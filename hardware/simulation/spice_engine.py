"""Minimal synchronous ngspice shared-library runner; no package installation needed.
Uses KiCad's bundled macOS libngspice or NGSPICE_LIBRARY override.
"""
import ctypes as C
import os

class Vector(C.Structure):
    _fields_=[('name',C.c_char_p),('type',C.c_int),('flags',C.c_short),
              ('real',C.POINTER(C.c_double)),('complex',C.c_void_p),('length',C.c_int)]

class Spice:
    def __init__(self):
        self.messages=[]
        self.lib=C.CDLL(os.environ.get('NGSPICE_LIBRARY','/Applications/KiCad/KiCad.app/Contents/Frameworks/libngspice.0.dylib'))
        self.output=C.CFUNCTYPE(C.c_int,C.c_char_p,C.c_int,C.c_void_p)(self._output)
        self.exit=C.CFUNCTYPE(C.c_int,C.c_int,C.c_bool,C.c_bool,C.c_int,C.c_void_p)(self._exit)
        self.lib.ngSpice_Init.argtypes=[C.c_void_p]*7
        self.lib.ngSpice_Init.restype=C.c_int
        self.lib.ngSpice_Init(self.output,None,self.exit,None,None,None,None)
        self.lib.ngSpice_Command.argtypes=[C.c_char_p];self.lib.ngSpice_Command.restype=C.c_int
        self.lib.ngSpice_Circ.argtypes=[C.POINTER(C.c_char_p)];self.lib.ngSpice_Circ.restype=C.c_int
        self.lib.ngGet_Vec_Info.argtypes=[C.c_char_p];self.lib.ngGet_Vec_Info.restype=C.POINTER(Vector)
        self.command('set noaskquit');self.command('set nomoremode')
    def _output(self,text,*_):
        self.messages.append(text.decode(errors='replace'));return 0
    def _exit(self,*args):
        self.messages.append('CONTROLLED_EXIT '+str(args));return 0
    def command(self,text):
        start=len(self.messages)
        rc=self.lib.ngSpice_Command(text.encode())
        if rc or any('simulation(s) aborted' in m or 'doAnalyses:' in m for m in self.messages[start:]):
            raise RuntimeError((text,rc,self.messages[start:]))
    def load(self,deck):
        self.command('destroy all')
        lines=[s.encode() for s in deck.splitlines()]
        a=(C.c_char_p*(len(lines)+1))(*lines,None)
        start=len(self.messages);rc=self.lib.ngSpice_Circ(a)
        if rc:raise RuntimeError((rc,self.messages[start:]))
    def vector(self,name):
        v=self.lib.ngGet_Vec_Info(name.encode())
        if not v or not v.contents.real:raise RuntimeError(('missing vector',name,self.messages[-15:]))
        return [v.contents.real[i] for i in range(v.contents.length)]
    def value(self,name):return self.vector(name)[-1]
    def op(self):
        self.command('destroy all');self.command('op')
