from distutils.core import setup
from Cython.Build import cythonize
from distutils.extension import Extension
#这里为文件名
extensions = [
    Extension('ccsmain',['ccsmain.py'])
]
setup(ext_modules=cythonize(extensions))
