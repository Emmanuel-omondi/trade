import os
import sys
import subprocess

def build():
    root = os.path.dirname(__file__)
    cfile = os.path.join(root, 'feature_engine.c')
    if sys.platform.startswith('win'):
        target = os.path.join(root, 'feature_engine.dll')
        cmd = ['gcc', '-shared', '-o', target, cfile]
    elif sys.platform == 'darwin':
        target = os.path.join(root, 'libfeature_engine.dylib')
        cmd = ['gcc', '-shared', '-o', target, cfile]
    else:
        target = os.path.join(root, 'libfeature_engine.so')
        cmd = ['gcc', '-shared', '-fPIC', '-o', target, cfile]
    subprocess.run(cmd, check=True)
    return target

if __name__ == '__main__':
    build()
