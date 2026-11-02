// Native bootstrap: locate the original setup, unpack embedded source and run Tk.
// No administrator privileges, external shell, network or system Python required.
#ifndef UNICODE
#define UNICODE
#endif
#define _UNICODE
#include <windows.h>
#include <shlobj.h>
#include <shellapi.h>
#include <stdio.h>
#include <stdlib.h>
#include <wchar.h>
#include "payload_size.h"

static int setup_at(const wchar_t *path) {
    wchar_t test[32768];
    swprintf(test,32768,L"%ls\\python\\pythonw.exe",path);
    if(GetFileAttributesW(test)==INVALID_FILE_ATTRIBUTES)return 0;
    swprintf(test,32768,L"%ls\\llvm\\bin\\clang.exe",path);
    return GetFileAttributesW(test)!=INVALID_FILE_ATTRIBUTES;
}

static int find_setup(const wchar_t *path,wchar_t *result,int depth) {
    if(setup_at(path)){wcscpy(result,path);return 1;}
    if(!depth)return 0;
    wchar_t pattern[32768],child[32768];WIN32_FIND_DATAW entry;
    swprintf(pattern,32768,L"%ls\\TotK*",path);
    HANDLE scan=FindFirstFileW(pattern,&entry);
    if(scan==INVALID_HANDLE_VALUE)return 0;
    int found=0;
    do {
        if(!(entry.dwFileAttributes&FILE_ATTRIBUTE_DIRECTORY) || (entry.dwFileAttributes&FILE_ATTRIBUTE_REPARSE_POINT))continue;
        swprintf(child,32768,L"%ls\\%ls",path,entry.cFileName);
        if(find_setup(child,result,depth-1)){found=1;break;}
    }while(FindNextFileW(scan,&entry));
    FindClose(scan);return found;
}

static int fail(const wchar_t *message) {
    MessageBoxW(NULL,message,L"Instalador TotK Mod Menu",MB_OK|MB_ICONERROR);return 1;
}

int WINAPI wWinMain(HINSTANCE instance,HINSTANCE previous,LPWSTR tail,int show) {
    (void)previous;(void)tail;(void)show;
    int argc;wchar_t **argv=CommandLineToArgvW(GetCommandLineW(),&argc);
    HRSRC resource=FindResourceW(instance,MAKEINTRESOURCEW(101),RT_RCDATA);
    DWORD length=resource?SizeofResource(instance,resource):0;
    const unsigned char *bytes=resource?LockResource(LoadResource(instance,resource)):NULL;
    if(argc>1 && !wcscmp(argv[1],L"--selftest")) {
        int valid=bytes && length==PAYLOAD_SIZE && length>4 && bytes[0]=='P' && bytes[1]=='K';
        LocalFree(argv);return valid?0:1;
    }
    if(!bytes || length!=PAYLOAD_SIZE)return fail(L"O instalador esta incompleto. Baixe novamente o arquivo.");
    wchar_t folder[32768],archive[32768],setup[32768]={0},base[32768],python[32768];
    if(argc>2 && (!wcscmp(argv[1],L"--extract-only") || !wcscmp(argv[1],L"--ui-selftest"))) {
        wcsncpy(folder,argv[2],32767);folder[32767]=0;
    } else {
        if(!GetEnvironmentVariableW(L"LOCALAPPDATA",base,32768))return fail(L"Nao foi possivel localizar a pasta local do usuario.");
        swprintf(folder,32768,L"%ls\\TotKModMenu\\installer\\run-%lu-%llu",base,GetCurrentProcessId(),GetTickCount64());
    }
    if(SHCreateDirectoryExW(NULL,folder,NULL)!=ERROR_SUCCESS && GetFileAttributesW(folder)==INVALID_FILE_ATTRIBUTES)
        return fail(L"Nao foi possivel preparar a pasta do instalador.");
    swprintf(archive,32768,L"%ls\\payload.zip",folder);
    HANDLE file=CreateFileW(archive,GENERIC_WRITE,0,NULL,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,NULL);
    DWORD written=0;int okay=file!=INVALID_HANDLE_VALUE && WriteFile(file,bytes,length,&written,NULL) && written==length;
    if(file!=INVALID_HANDLE_VALUE)CloseHandle(file);
    if(!okay)return fail(L"Nao foi possivel extrair os arquivos do instalador.");
    if(argc>2 && !wcscmp(argv[1],L"--extract-only")){LocalFree(argv);return 0;}
    GetModuleFileNameW(NULL,base,32768);
    wchar_t *slash=wcsrchr(base,L'\\');if(slash)*slash=0;
    if(!find_setup(base,setup,2)) {
        if(SHGetFolderPathW(NULL,CSIDL_DESKTOPDIRECTORY,NULL,SHGFP_TYPE_CURRENT,base)==S_OK)
            find_setup(base,setup,2);
    }
    if(!setup[0]) {
        CoInitializeEx(NULL,COINIT_APARTMENTTHREADED);
        BROWSEINFOW browse={0};browse.lpszTitle=L"Selecione o setup original do recomp (pasta com python e llvm)";
        browse.ulFlags=BIF_RETURNONLYFSDIRS|BIF_NEWDIALOGSTYLE;
        PIDLIST_ABSOLUTE item=SHBrowseForFolderW(&browse);
        if(item){SHGetPathFromIDListW(item,setup);CoTaskMemFree(item);}
        CoUninitialize();
        if(!setup[0]){LocalFree(argv);return 0;}
        if(!setup_at(setup))return fail(L"Esta pasta nao contem o setup original. Procure a pasta com python, llvm e runtime.");
    }
    swprintf(python,32768,L"%ls\\python\\pythonw.exe",setup);
    // Paths are separate Python argv entries. Windows filenames cannot contain quotes.
    wchar_t *command=calloc(131072,sizeof(wchar_t));
    if(!command)return fail(L"Memoria insuficiente.");
    const wchar_t *code=L"import zipfile,sys,runpy,pathlib,traceback,ctypes\ntry:\n p=pathlib.Path(sys.argv[2]); zipfile.ZipFile(sys.argv[1]).extractall(p); sys.path.insert(0,str(p)); s=sys.argv[3]; t=sys.argv[4:]; sys.argv=['gui.py','--setup',s]+t; runpy.run_path(str(p/'gui.py'),run_name='__main__')\nexcept Exception:\n ctypes.windll.user32.MessageBoxW(0,traceback.format_exc(),'Falha ao abrir o instalador',16)\n sys.exit(1)\n";
    swprintf(command,131072,L"\"%ls\" -c \"%ls\" \"%ls\" \"%ls\" \"%ls\"%ls",python,code,archive,folder,setup,
             argc>1&&!wcscmp(argv[1],L"--ui-selftest")?L" --selftest":L"");
    STARTUPINFOW start={0};start.cb=sizeof(start);PROCESS_INFORMATION process;
    if(!CreateProcessW(python,command,NULL,NULL,FALSE,CREATE_NO_WINDOW,NULL,folder,&start,&process)) {
        free(command);LocalFree(argv);return fail(L"Nao foi possivel abrir o Python do setup original.");
    }
    free(command);
    int wait=argc>1&&!wcscmp(argv[1],L"--ui-selftest");
    LocalFree(argv);CloseHandle(process.hThread);
    DWORD status=0;if(wait){WaitForSingleObject(process.hProcess,60000);GetExitCodeProcess(process.hProcess,&status);}
    CloseHandle(process.hProcess);return (int)status;
}
