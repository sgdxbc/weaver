from weaver.prog import Expr, UpdateReg, Branch, NotConstant, Block


class StackContext:
    RUNTIME, HEADER, INSTANCE, SEQUENCE = 0, 1, 2, 3

    def __init__(self):
        self.reg_count = 100
        self.struct_count = 0
        self.reg_map = {}
        self.struct_map = {}


class LayerContext:
    def __init__(self, layer_id, stack):
        self.layer_id = layer_id
        self.stack = stack
        self.var_map = {}
        self.structs = set()
        self.inst_regs = set()

    def alloc_header_reg(self, bit, name):
        reg = HeaderReg(self.stack.reg_count, self.stack.struct_count, bit.length, name)
        self.var_map[bit] = self.stack.reg_count
        self.stack.reg_map[self.stack.reg_count] = reg
        if self.stack.struct_count not in self.stack.struct_map:
            self.stack.struct_map[self.stack.struct_count] = []
            self.structs.add(self.stack.struct_count)
        self.stack.struct_map[self.stack.struct_count].append(self.stack.reg_count)
        self.stack.reg_count += 1

    def finalize_struct(self):
        self.stack.struct_count += 1
        return self.stack.struct_count - 1

    def alloc_temp_reg(self, var, name):
        if var.length is not None:
            assert var.length % 8 == 0
            reg = TempReg(self.stack.reg_count, var.length // 8, name)
        else:
            reg = TempReg(self.stack.reg_count, None, name)
        self.var_map[var] = self.stack.reg_count
        self.stack.reg_map[self.stack.reg_count] = reg
        self.stack.reg_count += 1

    def alloc_inst_reg(self, var, name):
        assert var.init is not None
        if var.length is not None:
            assert var.length % 8 == 0
            reg = InstReg(
                self.stack.reg_count, self.layer_id, var.length // 8, var.init, name
            )
        else:
            reg = InstReg(self.stack.reg_count, self.layer_id, None, var.init, name)
        self.var_map[var] = self.stack.reg_count
        self.stack.reg_map[self.stack.reg_count] = reg
        self.inst_regs.add(self.stack.reg_count)
        self.stack.reg_count += 1

    def inst_expr(self):
        return compile6_inst_expr(self.layer_id)

    def prefetch_expr(self):
        return compile6_prefetch_expr(self.layer_id)


def compile6_inst_expr(layer_id):
    return f"l{layer_id}_i"


def compile6_prefetch_expr(layer_id):
    return f"l{layer_id}_f"


class HeaderReg:
    def __init__(self, reg_id, struct_id, bit_length, debug_name):
        self.reg_id = reg_id
        self.struct_id = struct_id
        self.debug_name = debug_name
        self.bit_length = bit_length

    def as_expr(self):
        return f"h{self.struct_id}->_{self.reg_id}"


class LocateStruct:
    def __init__(self, struct_id):
        self.struct_id = struct_id


def compile1_layout(layout, context):
    bits_pack = []
    pack_length = 0
    for name, bit in layout.name_map.items():
        if bit.length % 8 == 0:
            assert bits_pack == []
            context.alloc_header_reg(bit, layout.__name__ + "." + name)
        else:
            bits_pack.append((name, bit))
            pack_length += bit.length
            assert pack_length <= 8
            if pack_length == 8:
                bits_pack.reverse()
                for name, bit in bits_pack:
                    context.alloc_header_reg(bit, layout.__name__ + "." + name)
                bits_pack = []
                pack_length = 0
    struct_id = context.finalize_struct()
    return [LocateStruct(struct_id)]


def compile1_header_action(action, context):
    compiled_actions = []
    for sub_action in action.actions:
        compiled_actions += sub_action.compile1(context)
    return compiled_actions


class TempReg:
    def __init__(self, reg_id, byte_length, debug_name):
        self.reg_id = reg_id
        self.byte_length = byte_length
        self.debug_name = debug_name

    def as_expr(self):
        return f"${self.reg_id}"


class InstReg:
    def __init__(self, reg_id, layer_id, byte_length, initial_expr, debug_name):
        self.reg_id = reg_id
        self.layer_id = layer_id
        self.byte_length = byte_length
        self.initial_expr = initial_expr
        self.debug_name = debug_name

    def as_expr(self):
        return f"{compile6_inst_expr(self.layer_id)}->_{self.reg_id}"


def compile2_layout(layout, context):
    for name, bit in layout.name_map.items():
        context.alloc_temp_reg(bit, name)


def compile4_const(const):
    return Expr(set(), const, (const.value, f"Const({const.value})"))


def eval1_const(const):
    return const.value


def compile4_var(var, context):
    reg = context.var_map[var]
    return Expr(
        {reg},
        Eval1Var(reg),
        (
            context.stack.reg_map[reg].as_expr(),
            "$" + context.stack.reg_map[reg].debug_name,
        ),
    )


class Eval1Var:
    def __init__(self, reg):
        self.reg = reg

    def eval1(self, context):
        if self.reg in context:
            return context[self.reg]
        else:
            raise NotConstant()


def compile5_assign(assign, context):
    reg = context.var_map[assign.var]
    expr4 = assign.expr.compile4(context)
    text = "\n".join(
        [
            f"// {context.stack.reg_map[reg].debug_name} = {expr4.compile6[1]}",
            f"{context.stack.reg_map[reg].as_expr()} = {expr4.compile6[0]};",
        ]
    )
    return [UpdateReg(reg, expr4, False, text)]


def compile5_action(action, context):
    action5 = []
    for stat in action.stats:
        action5 += stat.compile5(context)
    return action5


def compile4_op2(name, expr1, expr2, context):
    expr1_4 = expr1.compile4(context)
    expr2_4 = expr2.compile4(context)
    return Expr(
        expr1_4.read_regs | expr2_4.read_regs,
        Eval1Op2(name, expr1_4, expr2_4),
        (
            compile6h_op2(name, expr1_4.compile6[0], expr2_4.compile6[0]),
            compile6h_op2(name, expr1_4.compile6[1], expr2_4.compile6[1]),
        ),
    )


class Eval1Op2:
    def __init__(self, name, expr1, expr2):
        self.name = name
        self.expr1 = expr1
        self.expr2 = expr2

    def eval1(self, context):
        expr1_eval1 = self.expr1.eval1(context)
        expr2_eval1 = self.expr2.eval1(context)
        if self.name == "add":
            return expr1_eval1 + expr2_eval1
        elif self.name == "sub":
            return expr1_eval1 - expr2_eval1
        elif self.name == "left_shift":
            return expr1_eval1 << expr2_eval1
        elif self.name == "slice_before":
            return expr1_eval1[expr2_eval1:]
        elif self.name == "slice_after":
            return expr1_eval1[:expr2_eval1]
        elif self.name == "slice_get":
            return expr1_eval1[expr2_eval1]
        else:
            assert False, "unknown op2"


def compile6h_op2(name, expr1, expr2):
    if name == "add":
        return f"({expr1}) + ({expr2})"
    elif name == "sub":
        return f"({expr1}) - ({expr2})"
    elif name == "left_shift":
        return f"({expr1}) << ({expr2})"
    elif name == "slice_before":
        return f"WV_SliceBefore({expr1}, {expr2})"
    elif name == "slice_after":
        return f"WV_SliceAfter({expr1}, {expr2})"
    elif name == "slice_get":
        return f"({expr1}).cursor[{expr2}]"
    else:
        assert False, f"unknown op2 {name}"


def compile4_op1(name, expr, context):
    expr4 = expr.compile4(context)
    return Expr(
        expr4.read_regs,
        Eval1Op1(name, expr4),
        (
            compile6h_op1(name, expr4.compile6[0]),
            compile6h_op1(name, expr4.compile6[1]),
        ),
    )


class Eval1Op1:
    def __init__(self, name, expr):
        self.name = name
        self.expr = expr

    def eval1(self, context):
        expr_eval1 = self.expr.eval1(context)
        if self.name == "slice_length":
            return len(expr_eval1)
        else:
            assert False, f"unknown op1 {self.name}"


def compile6h_op1(name, expr):
    if name == "slice_length":
        return f"({expr}).length"
    else:
        assert False, f"unknown op1 {name}"


def compile4_payload():
    return Expr({StackContext.HEADER}, Eval1Abstract(), ("current", "$payload"))


class Eval1Abstract:
    def eval1(self, context):
        raise NotConstant()


def compile0_prototype(prototype, context):
    header1 = prototype.header.compile1(context)
    if prototype.temp is not None:
        prototype.temp.compile2(context)
    # TODO: collect vexpr
    if prototype.selector is not None:
        inst3 = compile3_inst(prototype.selector, prototype.perm, context)
    else:
        inst3 = None
    return Layer(
        header1, inst3, prototype.preprocess, prototype.seq, prototype.psm, None
    )


def compile3_inst(selector, layout, context):
    for name, var in layout.name_map.items():
        context.alloc_inst_reg(var, name)
    # TODO: perm var from context
    if isinstance(selector, list):
        return Inst({context.var_map[var] for var in selector})
    else:
        vars1, vars2 = selector
        return BiInst(
            {context.var_map[var] for var in vars1},
            {context.var_map[var] for var in vars2},
        )


class Inst:
    def __init__(self, key_regs):
        self.key_regs = key_regs

    def compile5(self, context):
        return compile5_inst(self, context)


def compile5_inst(inst, context):
    fetch_route = [
        UpdateReg(
            StackContext.INSTANCE, Expr(set(), Eval1Abstract(), None), True, "fetch",
        ),
        *[
            UpdateReg(
                inst_reg,
                Expr({StackContext.INSTANCE}, Eval1Abstract(), None),
                False,
                f"// load {context.stack.reg_map[inst_reg].debug_name} from instance",
            )
            for inst_reg in context.inst_regs
        ],
    ]
    init_stats = []
    for inst_reg in context.inst_regs:
        initial_expr4 = context.stack.reg_map[inst_reg].initial_expr.compile4(context)
        init_stats.append(
            UpdateReg(
                inst_reg,
                initial_expr4[0],
                False,
                f"// initialize {context.stack.reg_map[inst_reg].debug_name} to {initial_expr4[1]}",
            )
        )
    create_route = [
        UpdateReg(
            StackContext.INSTANCE, Expr(set(), Eval1Abstract(), None), True, "create",
        ),
        *init_stats,
    ]
    return [
        UpdateReg(
            StackContext.INSTANCE,
            Expr(inst.key_regs, Eval1Abstract(), None),
            True,
            "prefetch",
        ),
        Branch(
            Expr({StackContext.INSTANCE}, Eval1Abstract(), ("...", "instance exist")),
            fetch_route,
            create_route,
        ),
        UpdateReg(
            StackContext.SEQUENCE,
            Expr({StackContext.INSTANCE}, Eval1Abstract(), None),
            False,
            "// load sequence state from instance",
        ),
    ]


class BiInst:
    def __init__(self, key_reg1, key_reg2):
        self.key_reg1 = key_reg1
        self.key_reg2 = key_reg2


class Layer:
    def __init__(self, header, inst, general, seq, psm, event):
        self.header = header
        self.inst = inst
        self.general = general
        self.seq = seq
        self.psm = psm
        self.event = event


def compile5_layer(layer, context):
    instr_list = [
        UpdateReg(
            StackContext.HEADER,
            Expr(set(), Eval1Abstract(), None),
            True,
            compile7_header(layer.header),
        ),
        *[
            UpdateReg(
                reg,
                Expr(StackContext.HEADER, Eval1Abstract(), None),
                False,
                f"// parse header -> ${context.stack.reg_map[reg].debug_name}",
            )
            for struct in context.structs
            for reg in context.stack.struct_map[struct]
        ],
    ]
    if layer.inst is not None:
        instr_list += layer.inst.compile5(context)
    if layer.general is not None:
        instr_list += layer.general.compile5(context)
    if layer.seq is not None:
        instr_list += compile5_seq(layer.seq, context)
    return Block(instr_list, None, None, None)


def compile7_header(header):
    return "// parse header"


def compile5_seq(seq, context):
    offset4 = seq.offset.compile4(context)
    data4 = seq.data.compile4(context)
    takeup4 = seq.takeup.compile4(context)
    return [
        UpdateReg(
            StackContext.SEQUENCE,
            Expr(
                offset4.read_regs | data4.read_regs | takeup4.read_regs,
                Eval1Abstract(),
                None,
            ),
            True,
            "insert",
        )
    ]
