from rubik.util import indent_join, make_block, code_comment
from mako.template import Template


def compile7_branch(branch):
    return code_comment(
        "\n".join(
            [
                f"if ({branch.pred.compile6[0]}) "
                + indent_join(stat.compile7 for stat in branch.yes_list)
                + " else "
                + indent_join(stat.compile7 for stat in branch.no_list),
            ]
        ),
        f"IF {branch.pred.compile6[1]}",
    )


def compile7_block(block, is_entry, layer_id):
    if is_entry:
        prefix = f"L{layer_id}: "
    else:
        prefix = f"B{block.block_id}: "
    if block.pred is not None:
        escape = code_comment(
            f"if ({block.pred.compile6[0]}) goto B{block.yes_block.block_id}; "
            f"else goto B{block.no_block.block_id};",
            f"BRANCH {block.pred.compile6[1]}",
        )
    else:
        escape = "goto G_Shower;"
    return prefix + indent_join(
        [*[instr.compile7 for instr in block.instr_list], escape]
    )


# really want to use `$123` instead of `_123` for every register
# i.e. `h42->$123` for header registers and `l0_i->$123` for instance registers
# and use `_123` for names derived from corresponding registers
# i.e. `l0_f->k._123`
# unfortunately, GDB use $123 as reference to result of expression no.123 in
# interactive session
# revert it to original idea if there's any way to tweak GDB pls
def decl_reg(reg, prefix="_"):
    if reg.byte_length is not None:
        type_decl = f"WV_U{reg.byte_length * 8}"
        post = ""
    else:
        type_decl = "WV_ByteSlice"
        post = " = WV_EMPTY"
    return f"{type_decl} {prefix}{reg.reg_id}{post};  // {reg.debug_name}"


def decl_header_reg(reg):
    if not hasattr(reg, "bit_length"):  # for SliceKeyReg
        prefix = "WV_Byte"
        postfix = f"[{reg.index}]"
    elif reg.bit_length is None:  # only in event layout
        prefix = "WV_ByteSlice"
        postfix = ""
    elif reg.bit_length < 8:
        prefix = "WV_U8"
        postfix = f": {reg.bit_length}"
    else:
        prefix = f"WV_U{reg.bit_length}"
        postfix = ""
    return f"{prefix} _{reg.reg_id}{postfix};  // {reg.debug_name}"


def compile7_stack(stack, block_map, inst_decls, entry_id, layer_context_map):
    struct7 = Template(
        r"""
## prefix7
#include <weaver.h>
#include <tommyds/tommyhashdyn.h>
#if TOMMY_SIZE_BIT == 64
#define hash(k, s) tommy_hash_u64(0, k, s)
#else
#define hash(k, s) tommy_hash_u32(0, k, s)
#endif
## struct7
% for struct, regs in stack.struct_map.items():
typedef struct {
  % for reg in regs:
  ${decl_header_reg(stack.reg_map[reg])}
  % endfor
}__attribute__((packed)) H${struct};
% endfor
## extern_call7
% for call, struct_id in stack.call_struct.items():
WV_U8 ${call.layout.debug_name}(H${struct_id} *, WV_Any *);
% endfor
## inst_struct7
% for inst_decl in inst_decls.values():
${inst_decl.compile7}
% endfor
## eq_func7
% for i in range(layer_count):
% if i in inst_decls:
int l${i}_eq(const void *key, const void *object) {
  return memcmp(key, object, sizeof(${compile6_key_type(i)}));
}
% endif
% endfor
## runtime7
struct _WV_Runtime {
  WV_Profile profile;
  WV_U64 packet_count;
  % for i in range(layer_count):
  % if i in inst_decls:
  ${compile6_inst_type(i)} *l${i}_p;
  tommy_hashdyn t${i};
  TIMER_FIELDS(${compile6_inst_type(i)})
  % endif
  % endfor
};
WV_Runtime *WV_AllocRuntime() {
  WV_Runtime *rt = WV_Malloc(sizeof(WV_Runtime));
  rt->packet_count = 0;
  % for i in range(layer_count):
  % if i in inst_decls:
  tommy_hashdyn_init(&rt->t${i});
  rt->l${i}_p = WV_Malloc(sizeof(${compile6_inst_type(i)}));
  memset(rt->l${i}_p, 0, sizeof(${compile6_inst_type(i)}));
  TIMER_INIT(rt, ${compile6_inst_type(i)});
  % endif
  % endfor
  return rt;
}
WV_U8 WV_FreeRuntime(WV_Runtime *rt) {
  // todo
  return 0;
}
WV_Profile *WV_GetProfile(WV_Runtime *rt) {
  return &rt->profile;
}
WV_U8 TimerCleanup(WV_Runtime *rt) {
  WV_Runtime *runtime = rt;
  struct timeval tv;
  gettimeofday(&tv, NULL);
  WV_U64 now = tv.tv_sec;
  % for i in range(layer_count):
  % if i in inst_decls:
  <% last_ptr = f'rt->{compile6_inst_type(i)}_timer_last' %>
  while (${last_ptr} != NULL && ${last_ptr}->last_update + TIMEOUT < now) {
    ${compile6_inst_type(i)} *${layer_context_map[i].inst_expr6} = ${last_ptr};
    ${layer_context_map[i].inst.destroy(layer_context_map[i]).compile7}
    ${last_ptr} = ${last_ptr}->prev;
  }
  if (${last_ptr} == NULL) {
    rt->${compile6_inst_type(i)}_timer_head = NULL;
  }
  % endif
  % endfor
  return 0;
}
"""
    ).render(
        stack=stack,
        inst_decls=inst_decls,
        layer_count=len(block_map),
        compile6_key_type=compile6_key_type,
        compile6_inst_type=compile6_inst_type,
        decl_header_reg=decl_header_reg,
        layer_context_map=layer_context_map
    )

    layer_count = len(block_map)
    raw_blocks7 = {
        block.block_id: compile7_block(block, block is entry, layer_id)
        for layer_id, entry in block_map.items()
        for block in entry.recursive()
    }
    blocks7 = {
        block_id: block7.replace("%%BLOCK_ID%%", str(block_id))
        for block_id, block7 in raw_blocks7.items()
    }

    process7 = (
        "WV_U8 WV_ProcessPacket(WV_ByteSlice packet, WV_Runtime *runtime) "
        + indent_join(
            [
                *[
                    'if (runtime->packet_count++ == 1000000) ' + make_block(
                        'runtime->packet_count = 0;\n'
                        'TimerCleanup(runtime);'
                    )
                ],
                *[
                    f"H{struct} *{compile6_struct_expr(struct)};"
                    for struct in stack.struct_map
                ],
                *[
                    f"H{struct} h{struct}_c; h{struct} = &h{struct}_c;"
                    for struct in stack.call_struct.values()
                ],
                *[
                    f"WV_ByteSlice {compile6_content(layer)};\n"
                    + f"WV_Byte *{compile6_need_free(layer)} = NULL;"
                    for layer in range(layer_count)
                ],
                *[
                    f"{compile6_inst_type(layer)} *{compile6_inst_expr(layer)};\n"
                    + f"{compile6_prefetch_type(layer)} *{compile6_prefetch_expr(layer)};"
                    for layer in range(layer_count)
                    if layer in inst_decls
                ],
                *[
                    f"WV_U16 b{block_id}_t;"
                    for block_id in blocks7
                    if raw_blocks7[block_id] != blocks7[block_id]
                ],
                *[
                    decl_reg(reg, "_")
                    for reg in stack.reg_map.values()
                    # todo
                    if not hasattr(reg, "layer_id")
                    and not hasattr(reg, "struct_id")
                    and not hasattr(reg, "slice_reg6")
                ],
                "WV_ByteSlice current = packet, saved;",
                "WV_I32 return_target = -1;",
                f"goto L{entry_id};",
                "G_Shower: "
                + make_block(
                    "switch (return_target) "
                    + indent_join(
                        [
                            *[
                                f"case {block_id}: goto B{block_id}_R;"
                                for block_id in blocks7
                                if raw_blocks7[block_id] != blocks7[block_id]
                            ],
                            "default: goto G_End;",
                        ]
                    )
                ),
                "G_End: "
                + indent_join(
                    [
                        *[
                            f"if (l{layer}_nf) WV_Free(l{layer}_nf);"
                            for layer in range(layer_count)
                        ],
                        "return 0;",
                    ]
                ),
                *blocks7.values(),
            ]
        )
    )

    return "\n".join([struct7, process7])


def compile7w_stack(stack):
    default7 = r"""
WV_U8 WV_Setup() {
  return 0;
}    
"""
    extern_call7 = "\n".join(
        "typedef struct "
        + indent_join(
            decl_header_reg(stack.reg_map[reg]) for reg in stack.struct_map[struct_id]
        )
        + f"__attribute__((packed)) H{struct_id};\n"
        + f"WV_U8 {call.layout.debug_name}(H{struct_id} *args, WV_Any *user_data) "
        + make_block("return 0;")
        for call, struct_id in stack.call_struct.items()
    )
    return "\n".join(["#include <weaver.h>", default7, extern_call7])


def compile6_inst_type(layer_id):
    return f"L{layer_id}I"


def compile6_key_type(layer_id):
    return f"L{layer_id}K"


def compile6_rev_key_type(layer_id):
    return f"L{layer_id}RK"


def compile6_prefetch_type(layer_id):
    return f"L{layer_id}F"


def compile6_inst_expr(layer_id):
    return f"l{layer_id}_i"


def compile6_struct_expr(struct_id):
    return f"h{struct_id}"


def compile6_content(layer_id):
    return f"l{layer_id}_c"


def compile6_need_free(layer_id):
    return f"l{layer_id}_nf"


def compile6_prefetch_expr(layer_id):
    return f"l{layer_id}_p"


def compile7_decl_inst(inst, context):
    return (
        "typedef struct "
        + indent_join(
            decl_header_reg(context.stack.reg_map[reg]) for reg in inst.key_regs
        )
        + f" {compile6_key_type(context.layer_id)};\n"
        + f"typedef struct {compile6_inst_type(context.layer_id)} "
        + indent_join(
            [
                f"{compile6_key_type(context.layer_id)} k;",
                "tommy_node node;",
                "WV_Seq seq;",
                "WV_Any user_data;",
                f"TIMER_INJECT_FIELDS({compile6_inst_type(context.layer_id)})",
                *[decl_reg(context.stack.reg_map[reg]) for reg in inst.inst_regs],
            ]
        )
        + f" {compile6_inst_type(context.layer_id)}, {compile6_prefetch_type(context.layer_id)};"
    )


def compile7_decl_bi_inst(bi_inst, context):
    return (
        "typedef struct "
        + indent_join(
            decl_header_reg(context.stack.reg_map[reg])
            for reg in bi_inst.key_regs1 + bi_inst.key_regs2 + bi_inst.dual_regs
        )
        + f" {compile6_key_type(context.layer_id)};\n"
        + "typedef struct "
        + indent_join(
            decl_header_reg(context.stack.reg_map[reg])
            for reg in bi_inst.key_regs2 + bi_inst.key_regs1 + bi_inst.dual_regs
        )
        + f" {compile6_rev_key_type(context.layer_id)};\n"
        + f"typedef struct {compile6_inst_type(context.layer_id)} "
        + indent_join(
            [
                f"{compile6_key_type(context.layer_id)} k;",
                "WV_U8 flag;",
                "tommy_node node;",
                "WV_Seq seq;",
                "WV_Any user_data;",
                f"{compile6_rev_key_type(context.layer_id)} k_rev;",
                "WV_U8 flag_rev;",
                "tommy_node node_rev;",
                "WV_Seq seq_rev;",
                "WV_Any user_data_rev;",
                f"TIMER_INJECT_FIELDS({compile6_inst_type(context.layer_id)})",
                *[decl_reg(context.stack.reg_map[reg]) for reg in bi_inst.inst_regs],
            ]
        )
        + f" {compile6_inst_type(context.layer_id)};\n"
        + "typedef struct "
        + indent_join(
            [
                f"{compile6_key_type(context.layer_id)} k;",
                "WV_U8 reversed;",
                "tommy_node node;",
                "WV_Seq seq;",
                "WV_Any user_data;",
            ]
        )
        + f" {compile6_prefetch_type(context.layer_id)};"
    )
