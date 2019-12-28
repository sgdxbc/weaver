from weaver.misc.code import *
from weaver.code import *
from weaver.writer_context import GlobalContext

b1 = BasicBlock.from_codes(ip)
b2 = b1.optimize()
context = GlobalContext({})
context.execute_block_recurse(b2, 0)
print(context.write_all(b2, 1))
