#!/usr/bin/python3
# Functions for interacting with bash commands

import sys
import subprocess

from sd.common import flatten
from sd.common import warn, error


# Simpler version for copy pasta:
# code = subprocess.run(cmd, check=False).returncode


# Simple version for copy pasta
def qrun(*args, encoding='utf-8', check=True, errors='replace', **kargs):
    "Quickrun with strict checking, no flatten command"
    args = args[0] if len(args) == 1 else args
    ret = subprocess.run(args, check=check, stdout=subprocess.PIPE, **kargs)
    return ret.stdout.decode(encoding=encoding, errors=errors).splitlines() if ret.stdout else []


def bool_run(*args):
    "Run cmd and return True if it succeded, else False"
    args = args[0] if len(args) == 1 else args
    code = subprocess.run(args, check=False,).returncode
    return not bool(code)


def srun(*cmds, **kargs):
    "Split all text before quick run"
    return quickrun(flatten([str(item).split() for item in cmds]), **kargs)


def shell(cmd, **kargs):
    "Return first line of stdout"
    return quickrun(cmd, **kargs)[0].strip()


def quickrun(*cmd, check=True, encoding='utf-8', errors='replace', mode='w', stdin=None,
             verbose=0, testing=False, ofile=None, trifecta=False, printme=False, hidewarning=False, **kargs):
    '''Run a command, list of commands as arguments or any combination therof and return
    the output is a list of decoded lines.
    check       = if the process exits with a non-zero exit code then quit
    hidewarning = Don't print errors
    testing     = Print command and don't do anything.
    ofile       = output file
    mode        = output file write mode
    trifecta    = return (returncode, stdout, stderr)
    stdin       = standard input (auto converted to bytes)
    printme     = Print to stdout instead of returning it, returns code instead
    '''
    # Checks
    if printme and trifecta:
        error("quickrun cant use both printme and trifecta")
    if hidewarning and check:
        error("Printing errors makes no sense when check=True")

    # Build command
    cmd = list(map(str, flatten(cmd)))
    if len(cmd) == 1:
        cmd = cmd[0]
    if testing:
        print("Not running command:", cmd)
        return []
    if verbose:
        print("Running command:", cmd)
        print("               =", ' '.join(cmd))


    # Choose output file
    if ofile:
        output = open(ofile, mode=mode)
    else:
        output = subprocess.PIPE


    # Choose stdin
    if stdin:
        if type(stdin) != bytes:
            stdin = stdin.encode()

    if printme:
        # todo: make more realtime https://stackoverflow.com/questions/803265/getting-realtime-output-using-subprocess
        ret = subprocess.run(cmd, check=check, stdout=sys.stdout, stderr=sys.stderr, input=stdin, **kargs)
        code = ret.returncode

    else:
        # Run the command and get return value
        ret = subprocess.run(cmd, check=check, stdout=output, stderr=output, input=stdin, **kargs)
        code = ret.returncode
        stdout = ret.stdout.decode(encoding=encoding, errors=errors).splitlines() if ret.stdout else []
        stderr = ret.stderr.decode(encoding=encoding, errors=errors).splitlines() if ret.stderr else []

    if ofile:
        output.close()
        return []

    if trifecta:
        return code, stdout, stderr

    if code and not hidewarning:
        warn("Process returned code:", code)

    if printme:
        return ret.returncode

    if not hidewarning:
        for line in stderr:
            print(line)

    return stdout


def run(*args, **kargs):
    warn("run is being deprecated! Check your script!")
    return srun(*args, **kargs)
