from __future__ import annotations
from typing import TYPE_CHECKING, Dict
from weaver.util import make_block

if TYPE_CHECKING:
    from weaver.code import Reg
    from weaver.writer_context import InstrContext


class RegTable:
    def __init__(self):
        self.regs: Dict[Reg, RegAux] = {}

    def __getitem__(self, reg: Reg):
        return self.regs[reg]

    count = 0

    def __setitem__(self, reg: Reg, aux: RegAux):
        assert reg not in self.regs
        self.regs[reg] = aux
        self.count = max(self.count, reg + 1)

    def alloc(self, aux: RegAux) -> int:
        reg_id = self.count
        self[reg_id] = aux
        return reg_id

    def write(self, context: InstrContext, reg: Reg) -> str:
        return self[reg].value_name(context, reg)

    def decl(self, reg: Reg) -> str:
        return self[reg].decl(reg)


reg_aux = RegTable()


class RegAux:
    def __init__(self, byte_len: int = None, abstract: bool = False):
        if byte_len is not None:
            assert byte_len in {1, 2, 4, 8}
        self.byte_len = byte_len
        self.abstract = abstract

    def type_decl(self) -> str:
        assert not self.abstract
        if self.byte_len is not None:
            return f'WV_U{self.byte_len * 8}'
        else:
            return 'WV_ByteSlice'

    def value_name(self, context: InstrContext, reg: Reg) -> str:
        return f'_{reg}'

    def decl(self, reg: Reg) -> str:
        return f'{self.type_decl()} _{reg};'


class StructRegAux(RegAux):
    def __init__(self, byte_len: int, bit_len: int = None):
        if bit_len is not None:
            assert byte_len == 1
            assert 0 < bit_len <= 8
        super(StructRegAux, self).__init__(byte_len)
        self.bit_len = bit_len

    def value_name(self, context: InstrContext, reg: Reg) -> str:
        owner = context.recurse_context.global_context.struct_regs_owner[reg]
        return f'{owner.create_aux().name()}->_{reg}'

    def decl(self, reg: Reg) -> str:
        if self.bit_len is None:
            return super().decl(reg)
        else:
            return f'{self.type_decl()} _{reg}: {self.bit_len};'


class HeaderStructAux:
    def __init__(self, struct):
        self.struct = struct

    def name(self) -> str:
        return f'h{self.struct.struct_id}'

    def typedef(self) -> str:
        return f'H{self.struct.struct_id}'

    def sizeof(self) -> str:
        return f'sizeof({self.typedef()})'

    def declare_type(self) -> str:
        fields_text = make_block('\n'.join(reg_aux.decl(reg)
                                           for reg in self.struct.regs))
        return f'typedef struct {fields_text} {self.typedef()};'

    def declare_pointer(self) -> str:
        return f'{self.typedef()} *{self.name()};'

    @staticmethod
    def create(struct):
        return HeaderStructAux(struct)


class DataStructAux(HeaderStructAux):
    def __init__(self, key_regs, struct):
        super().__init__(struct)
        self.key_regs = key_regs

    def declare_type(self) -> str:
        assert False, 'data struct should not be declared as header struct'

    def declare_inst_type(self, layer_id, bi) -> str:
        if not bi:
            key_struct_text = 'typedef struct ' + make_block('\n'.join(
                reg_aux.decl(reg) for reg in self.key_regs
            )) + f' {DataStructAux.key_struct_type(layer_id)};'
            inst_struct_text = 'typedef struct ' + make_block('\n'.join(
                [
                    f'{DataStructAux.key_struct_type(layer_id)} k;', 
                    'tommy_node node;'
                    'WV_Seq seq;'
                ] + 
                [reg_aux.decl(reg) for reg in self.struct.regs]
            )) + f' {self.typedef()};'
            fetch_text = f'typedef {self.typedef()} L{layer_id}_Fetch;'
            return key_struct_text + '\n' + inst_struct_text + '\n' + fetch_text
        else:
            assert False

    @staticmethod
    def key_struct_type(layer_id) -> str:
        return f'L{layer_id}_Key'


class DataStructAuxCreator:
    def __init__(self, key_regs):
        self.key_regs = key_regs

    def __call__(self, struct):
        return DataStructAux(self.key_regs, struct)
