from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from weaver.code import BasicBlock


class BlockGroupAux:
    def __init__(self):
        self.callee_block: Optional[BasicBlock] = None
        self.table_index: Optional[int] = None

    def callee_label(self):
        if self.callee_block is None:
            return 'L_End'
        else:
            return f'L{self.callee_block.block_id}'


class RegGroupAux:
    def __init__(self):
        self.regs = {}

    def __getitem__(self, reg: int):
        return self.regs[reg]

    count = 0

    def __setitem__(self, reg: int, aux: 'RegAux'):
        assert reg not in self.regs
        self.regs[reg] = aux
        self.count = max(self.count, reg + 1)

    def alloc(self, aux: 'RegAux') -> int:
        reg_id = self.count
        self[reg_id] = aux
        return reg_id


reg_aux = RegGroupAux()


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


class ValueAux:
    def __init__(self, cexpr_template: str):
        self.cexpr_template = cexpr_template
        self.block: Optional[BasicBlock] = None


class InstValueAux(ValueAux):
    def __init__(self, key):
        super().__init__('<should not use>')
        self.key = key

    def write(self):
        assert self.block is not None
        return f'table_{self.block.group_aux.table_index}_inst->{self.key}'


class InstrAux:
    def __init__(self):
        self.block: Optional[BasicBlock] = None
