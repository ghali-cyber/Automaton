import pathlib, runpy, sys

base=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(base))
runpy.run_path(str(base/'control.py'),run_name='__main__')
