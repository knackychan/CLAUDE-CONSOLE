"""Windows atomic text writes with the temporary file reserved through replacement (plan 54)."""
import ctypes
from ctypes import wintypes
import msvcrt
import os

_kernel = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                               wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
_kernel.CreateFileW.restype = wintypes.HANDLE
_kernel.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel.SetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
_kernel.SetFileInformationByHandle.restype = wintypes.BOOL


class _RenameInfo(ctypes.Structure):
    _fields_ = [("Flags", wintypes.DWORD), ("RootDirectory", wintypes.HANDLE),
                ("FileNameLength", wintypes.DWORD), ("FileName", wintypes.WCHAR * 1)]


def write_text(source, destination, text):
    # Hold DELETE access from creation so a later metadata reader cannot force us to reopen the temp file.
    handle = _kernel.CreateFileW(os.path.abspath(source), 0x40010000, 7, None, 2, 0x80, None)
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        fd = msvcrt.open_osfhandle(handle, os.O_WRONLY | os.O_BINARY)
    except BaseException:
        _kernel.CloseHandle(handle)
        raise
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(text)
        stream.flush()
        try:
            os.replace(source, destination)
        except OSError as exc:
            if getattr(exc, "winerror", None) not in (5, 32):
                raise
            name = os.path.abspath(destination).encode("utf-16-le")
            info = ctypes.create_string_buffer(_RenameInfo.FileName.offset + len(name) + 2)
            header = _RenameInfo.from_buffer(info)
            header.Flags, header.FileNameLength = 3, len(name)  # REPLACE_IF_EXISTS | POSIX_SEMANTICS
            ctypes.memmove(ctypes.addressof(info) + _RenameInfo.FileName.offset, name, len(name))
            if not _kernel.SetFileInformationByHandle(handle, 22, info, len(info)):  # FileRenameInfoEx
                error = ctypes.get_last_error()
                if error in (1, 50, 87):  # native mode unsupported: keep the original replacement error
                    raise
                raise ctypes.WinError(error)
