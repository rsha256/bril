# Your first Bril optimizer

Writing an optimizer (or any tool) for Bril 
 boils down to reading in a JSON file, manipulating it, and writing it back out.
You can then pipe these tools together to build more complex tools.
For example, this directory contains a simple Python script that removes `nop` instructions.

Before you start, make sure you have the Bril tools installed using the [`install.sh`](../../install.sh) script.

Not many programs have `nops` in them,
 but the [`adler32`](../../benchmarks/mem/adler32.bril) benchmark does!

Try running the following to run your optimizer:
```sh
cat ../../benchmarks/mem/adler32.bril | bril2json | python3 remove_nops.py | bril2txt
```

And we can check that we didn't mess things up too bad by running the reference interpreter `brili`:
```sh
cat ../../benchmarks/mem/adler32.bril | bril2json | brili -p
cat ../../benchmarks/mem/adler32.bril | bril2json | python3 remove_nops.py | brili -p
```

By passing the `-p` flag to `brili`, we see profiling information about the execution of the program (just the number of instructions executed).

The [`brench`](https://capra.cs.cornell.edu/bril/tools/brench.html) 
 tool can be used to orchestrate running benchmarks and comparing the output of different passes.
This directory includes and example TOML file to configure `brench` to
 run the `remove_nops` pass on call the benchmarks in the `benchmarks` directory.
Check out the `brench.toml` file and run the following to see the results:
```sh
brench brench.toml
```

The `brench` tool will run the given benchmarks
 and compare their output (on `stdout`) to ensure they match.
It will then extract a number to be the results 
 (in this case, the number of instructions executed) 
 from `stderr` and print a csv of the results.

Great! You saved a few cycles by removing those `nop`s. Now go write a more interesting optimizer!