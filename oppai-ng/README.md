difficulty and pp calculator for osu!, with some modifications for [gulag](https://github.com/cmyui/gulag) (mostly relax support)

this is a wrapper around the actual oppai-ng implementation you can view [here](https://github.com/Francesco149/oppai-ng)

to build, all you have to do is run `./build`

and then move the pyd/so file (OS-dependent) file to wherever you would like to import from.

example usage:

```py
import oppai

with oppai.OppaiWrapper() as ezpp: # has __enter__ and __exit__ to manage c memory for you
  ezpp.configure(mode=0, acc=99.5, mods=0, combo=100, nmiss=2) # positional is optional, but must be provided in this order if not
  ezpp.calculate("example map path.osu") # you can also pass bytes to ezpp.calculate_data(bytes)
  
  pp = ezpp.get_pp()
  sr = ezpp.get_sr()
```