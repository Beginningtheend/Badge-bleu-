/*
 * bdfpdf.dll — DLL d'export PDF minimaliste pour le programme de test synthétique bdfedit.
 * Rôle dans le labo : dépendance OPTIONNELLE absente du système (classe A, déclarative :
 * « DLL manquante, à fournir depuis le catalogue avec empreinte »). Elle écrit un PDF 1.4 non
 * compressé, lisible par un outil indépendant (pdftotext).
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <string.h>

static int append(char **buf, size_t *len, size_t *cap, const char *s, size_t n)
{
    if (*len + n + 1 > *cap) {
        size_t ncap = (*cap + n + 1) * 2;
        char *nb = (char *)HeapReAlloc(GetProcessHeap(), 0, *buf, ncap);
        if (!nb) return 0;
        *buf = nb;
        *cap = ncap;
    }
    memcpy(*buf + *len, s, n);
    *len += n;
    (*buf)[*len] = 0;
    return 1;
}

static int appendf(char **buf, size_t *len, size_t *cap, const char *fmt, ...)
{
    char tmp[1024];
    va_list ap;
    va_start(ap, fmt);
    int n = _vsnprintf(tmp, sizeof(tmp), fmt, ap);
    va_end(ap);
    if (n < 0) return 0;
    return append(buf, len, cap, tmp, (size_t)n);
}

__declspec(dllexport) int __cdecl BdfPdfWriteText(const char *text, const wchar_t *out_path, unsigned long *bytes_written)
{
    size_t cap = 4096, len = 0;
    char *pdf = (char *)HeapAlloc(GetProcessHeap(), 0, cap);
    if (!pdf) return 1;
    /* flux de contenu */
    size_t ccap = 4096, clen = 0;
    char *content = (char *)HeapAlloc(GetProcessHeap(), 0, ccap);
    if (!content) return 1;
    append(&content, &clen, &ccap, "BT /F1 11 Tf 50 780 Td 14 TL\n", 29);
    const char *p = text;
    int lines = 0;
    while (*p && lines < 50) {
        const char *e = strchr(p, '\n');
        size_t n = e ? (size_t)(e - p) : strlen(p);
        append(&content, &clen, &ccap, "(", 1);
        for (size_t i = 0; i < n; i++) {
            unsigned char c = (unsigned char)p[i];
            if (c == '(' || c == ')' || c == '\\') { char esc[2] = {'\\', (char)c}; append(&content, &clen, &ccap, esc, 2); }
            else if (c < 32 || c > 126) append(&content, &clen, &ccap, "?", 1);
            else append(&content, &clen, &ccap, (const char *)&c, 1);
        }
        append(&content, &clen, &ccap, ") Tj T*\n", 8);
        lines++;
        if (!e) break;
        p = e + 1;
    }
    append(&content, &clen, &ccap, "ET\n", 3);

    long offs[6];
    appendf(&pdf, &len, &cap, "%%PDF-1.4\n%%\xE2\xE3\xCF\xD3\n");
    offs[1] = (long)len; appendf(&pdf, &len, &cap, "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n");
    offs[2] = (long)len; appendf(&pdf, &len, &cap, "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n");
    offs[3] = (long)len; appendf(&pdf, &len, &cap, "3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n");
    offs[4] = (long)len; appendf(&pdf, &len, &cap, "4 0 obj\n<< /Length %lu >>\nstream\n", (unsigned long)clen);
    append(&pdf, &len, &cap, content, clen);
    appendf(&pdf, &len, &cap, "endstream\nendobj\n");
    offs[5] = (long)len; appendf(&pdf, &len, &cap, "5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n");
    long xref = (long)len;
    appendf(&pdf, &len, &cap, "xref\n0 6\n0000000000 65535 f \n");
    for (int i = 1; i <= 5; i++) appendf(&pdf, &len, &cap, "%010ld 00000 n \n", offs[i]);
    appendf(&pdf, &len, &cap, "trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n%ld\n%%%%EOF\n", xref);

    HANDLE h = CreateFileW(out_path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) return 2;
    DWORD written = 0;
    BOOL ok = WriteFile(h, pdf, (DWORD)len, &written, NULL);
    FlushFileBuffers(h);
    CloseHandle(h);
    HeapFree(GetProcessHeap(), 0, pdf);
    HeapFree(GetProcessHeap(), 0, content);
    if (!ok || written != len) return 3;
    if (bytes_written) *bytes_written = (unsigned long)written;
    return 0;
}

BOOL WINAPI DllMain(HINSTANCE inst, DWORD reason, LPVOID reserved)
{
    (void)inst; (void)reason; (void)reserved;
    return TRUE;
}
