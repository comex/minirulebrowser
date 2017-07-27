from libc.stdlib cimport malloc, free
def normalize_rule_text_inner(text):
    as_bytes = text.rstrip().encode('utf-8')
    cdef int length = len(as_bytes)
    cdef char* inbuf = as_bytes
    cdef char* outbuf = <char *>malloc(len(as_bytes))
    cdef int i = 0
    cdef int j = 0
    cdef char c, d
    while i < length:
        c = inbuf[i]
        i += 1
        if (c >= 97 and c <= 122) or (c >= 48 and c <= 57):
            d = c
        elif c >= 65 and c <= 90:
            d = c + (97 - 65)
        else:
            continue
        outbuf[j] = d
        j += 1
    ret = outbuf[:j]
    free(outbuf)
    return ret
