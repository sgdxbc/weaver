# Weaver

![](https://github.com/sgdxbc/weaver/workflows/build/badge.svg)

First, run

```
$ make gen C=<config>
```

Set `<config>` to python module (**not** python file) you expect to generate from. Defaults to `stack_conf`, which reads `stack_conf.py` from project root. You can set it to `weaver.stock.stacks.tcp_ip` to use stock protocol stacks.

Two files named `weaver_blackbox.c` and `weaver_whitebox.template.c` will be generated. 

**Do NOT touch or read `weaver_blackbox.c`.**

Rename `weaver_whitebox.template.c` (to prevent overriding by next `make gen`) and edit it as you wish.

Run

```
$ make T=<target> A=<whitebox>
```

Set `<target>` to driver you wish to use (currently support: `pcap` and `dpdk`), and `<whitebox>` to path
to your edited code (defaults to `weaver_whitebox.c`).

For `dpdk` driver, make sure you have a compiled DPDK library and specified `RTE_SDK` envrionment 
variable before compilation.

An executable named `procpkts` will be built.

With `pcap` driver, run `procpkts` with pcap file name as argument. The packets in pcap file will be 
replayed forever, and throughput will be printed periodically. 

```
$ ./procpkts <pcap file>
```

Type Ctrl-C to exit.

With `dpdk` driver, run `procpkts` with the proper permission (as `root` or with `sudo`).
The execution command is as follows.

```
$ ./procpkts -l <L> -n <N> --proc-type=auto -- -p <P> --num-procs=<NP> --proc-id=<PID>
```

* `L` the lcore id, starting from 1
* `N` num of cores, should equal to NP
* `P` the mask of ports, e.g., 0x3 (0b11) for port 0 and 1
* `NP` num of cores, should equal to `N`
* `PID` the id of the process, starting from 0

The program will behave as a simple forwarding switch between the ports involved, and run the stack
on each of the incoming packets.

Type Ctrl-C to exit.

----

**UPDATE REQUIRED FOR FOLLOWING CONTENT.**

The `weaver` folder contains a Python module, with following files:
* `code.py` definitions of `Instr` (and its subclasses), `Value` (and its subclasses) and 
`BasicBlock`.
* `util.py`
* `auxiliary.py` definitions of `reg_aux`, which acts as a global symbol table for all registers, and 
`RegAux` with its subclasses, which are elements in `reg_aux`.
* `header.py` definitions of `Struct` and `ParseAction` (and its subclasses). `Struct` uses `reg_aux`
to construct information of itself.
* `writer.py` and `writer_context.py`. `writer.py` provides various kinds of `InstrWriter` and 
`ValueWriter` for `Instr`s and `Value`s to write themselves properly into specific context. 
`writer_context.py` contains `Context`s of different levels. A `GlobalContext` could write the whole
generated C program after executing all `BasicBlock`s.
* `__main__.py` command line interface.
* `stock` submodule provides pre-defined resources.

The `native` folder contains C code files which should be built along with generated code.
* `weaver.h` all-in-one universal definitions for generated code, runtime library and driver
* `runtime` platform-and-target-independent supporting data structures and functions, such as hash
table, reorder buffer, etc.
* `drivers` setup application in several environments. Each of code files in `drivers` implements an
entry point (e.g. `main` or equivalent) for application, so only one of them should be evolved in one
building process.