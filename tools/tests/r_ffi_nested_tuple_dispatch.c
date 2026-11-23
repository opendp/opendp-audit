/*
 * Test-only R ABI shim. No R interpreter or OpenDP native library is linked.
 * The three decoder function bodies below are extracted verbatim from
 * opendp/opendp@ef1a238634d6196b01a1a1e77d3d5ad2340e3094,
 * R/opendp/src/convert.c. Do not treat these tests as an R integration test.
 */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <setjmp.h>
#include <limits.h>

enum {VECSXP=1, STRSXP=2, REALSXP=3, INTSXP=4, LGLSXP=5};
typedef struct SexpObj *SEXP;
struct SexpObj {
    int kind;
    size_t len;
    SEXP *items;
    double *reals;
    int *integers;
    const char *text;
    SEXP origin, args;
};
typedef struct {void *ptr; size_t len;} FfiSlice;
typedef struct {const void *ptr;} ExtrinsicObject;
static struct SexpObj nil_value;
static SEXP R_NilValue = &nil_value;
static jmp_buf error_target;
static char last_error[256];

#define PROTECT(v) (v)
#define UNPROTECT(n) ((void)(n))
#define LENGTH(v) ((v)->len)
#define VECTOR_ELT(v, n) ((v)->items[n])
#define STRING_ELT(v, n) ((v)->items[n])
#define SET_VECTOR_ELT(v, n, x) ((v)->items[n] = (x))
#define SET_STRING_ELT(v, n, x) ((v)->items[n] = (x))
#define REAL(v) ((v)->reals)
#define INTEGER(v) ((v)->integers)
#define LOGICAL(v) ((v)->integers)

static void error(const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(last_error, sizeof(last_error), fmt, ap);
    va_end(ap);
    longjmp(error_target, 1);
}
static void error_unknown_type(const char *lhs, const char *rhs) {
    error("%s %s", lhs, rhs);
}
static SEXP allocVector(int kind, size_t len) {
    SEXP v = calloc(1, sizeof(*v));
    if (!v) {fputs("out of memory\n", stderr); exit(2);}
    v->kind = kind;
    v->len = len;
    if (kind == VECSXP || kind == STRSXP) v->items = calloc(len+1, sizeof(SEXP));
    if (kind == REALSXP) v->reals = calloc(len+1, sizeof(double));
    if (kind == INTSXP || kind == LGLSXP) v->integers = calloc(len+1, sizeof(int));
    return v;
}
static SEXP mkChar(const char *text) {
    SEXP v = allocVector(STRSXP, 0);
    v->text = text;
    return v;
}
static SEXP get_origin(SEXP type_name) {return type_name->origin;}
static SEXP get_args(SEXP type_name) {return type_name->args;}
static const char *sexp_to_charptr(SEXP value) {return value->text;}
static unsigned char str_equal(const char *a, const char *b) {return strcmp(a,b)==0;}
static unsigned char is_in(const char *v, const char **arr) {
    for (size_t i=0; arr[i]; i++) if (str_equal(v, arr[i])) return 1;
    return 0;
}
static const char *ATOM_TYPES[] = {
    "u8", "u16", "u32", "u64", "i8", "i16", "i32", "i64",
    "f32", "f64", "usize", "bool", "String", NULL
};
static SEXP extrinsic_object_to_sexp(const ExtrinsicObject *p) {
    (void)p;
    fputs("unexpected extrinsic conversion\n", stderr);
    exit(3);
}
static SEXP slice_to_vector(FfiSlice *raw, SEXP ty);
static SEXP slice_to_bitvector(FfiSlice *raw, SEXP ty);
static SEXP slice_to_hashmap(FfiSlice *raw, SEXP ty);
static SEXP slice_to_scalar(FfiSlice *raw, SEXP ty);

/* Begin exact, unedited upstream decoder functions. */
SEXP voidptr_to_sexp(void *input, SEXP rust_type, size_t len)
{
    PROTECT(rust_type);
    const char *c_origin = sexp_to_charptr(get_origin(rust_type));
    SEXP result;

    if (str_equal(c_origin, "String"))
    {
        // STRSXP is a vector of strings, where each element is a string
        result = PROTECT(allocVector(STRSXP, len));
        for (int i = 0; i < len; i++)
            SET_STRING_ELT(result, i, mkChar(((char **)input)[i]));
        UNPROTECT(1);
    }
    else if (str_equal(c_origin, "f64"))
    {
        result = PROTECT(allocVector(REALSXP, len));
        for (int i = 0; i < len; i++)
        {
            REAL(result)
            [i] = ((double *)input)[i];
        }
        UNPROTECT(1);
    }
    else if (str_equal(c_origin, "f32"))
    {
        result = PROTECT(allocVector(REALSXP, len));
        for (int i = 0; i < len; i++)
        {
            float input_f32 = ((float *)input)[i];
            REAL(result)
            [i] = (double)input_f32;
        }
        UNPROTECT(1);
    }
    else if (str_equal(c_origin, "i32"))
    {
        result = PROTECT(allocVector(INTSXP, len));
        for (int i = 0; i < len; i++)
        {
            INTEGER(result)
            [i] = ((int *)input)[i];
        }
        UNPROTECT(1);
    }
    else if (str_equal(c_origin, "i16"))
    {
        result = PROTECT(allocVector(INTSXP, len));
        for (int i = 0; i < len; i++)
            INTEGER(result)[i] = (int)((short *)input)[i];
        UNPROTECT(1);
    }
    else if (str_equal(c_origin, "i8"))
    {
        result = PROTECT(allocVector(INTSXP, len));
        for (int i = 0; i < len; i++)
            INTEGER(result)[i] = (int)((signed char *)input)[i];
        UNPROTECT(1);
    }
    else if (str_equal(c_origin, "u32"))
    {
        result = PROTECT(allocVector(INTSXP, len));
        for (int i = 0; i < len; i++)
        {
            unsigned int input_u32 = ((unsigned int *)input)[i];
            if (input_u32 > INT_MAX)
                error("u32 cannot be greater than INT_MAX");
            INTEGER(result)
            [i] = (int)input_u32;
        }
        UNPROTECT(1);
    }
    else if (str_equal(c_origin, "i64"))
    {
        result = PROTECT(allocVector(INTSXP, len));
        for (int i = 0; i < len; i++)
        {
            long int input_i64 = ((long int *)input)[i];
            if (input_i64 > INT_MAX)
                error("i64 cannot be greater than INT_MAX");
            if (input_i64 < INT_MIN)
                error("i64 cannot be less than INT_MIN");
            INTEGER(result)
            [i] = (int)input_i64;
        }
        UNPROTECT(1);
    }
    else if (str_equal(c_origin, "u16"))
    {
        result = PROTECT(allocVector(INTSXP, len));
        for (int i = 0; i < len; i++)
            INTEGER(result)[i] = (int)((unsigned short *)input)[i];
        UNPROTECT(1);
    }
    else if (str_equal(c_origin, "u8"))
    {
        result = PROTECT(allocVector(INTSXP, len));
        for (int i = 0; i < len; i++)
            INTEGER(result)[i] = (int)((unsigned char *)input)[i];
        UNPROTECT(1);
    }
    else if (str_equal(c_origin, "u64"))
    {
        result = PROTECT(allocVector(INTSXP, len));
        for (int i = 0; i < len; i++)
        {
            long unsigned int input_u64 = ((long unsigned int *)input)[i];
            if (input_u64 > INT_MAX)
                error("u64 cannot be greater than INT_MAX");
            INTEGER(result)
            [i] = (int)input_u64;
        }
        UNPROTECT(1);
    }
    else if (str_equal(c_origin, "usize"))
    {
        result = PROTECT(allocVector(INTSXP, len));
        for (int i = 0; i < len; i++)
        {
            size_t input_size_t = ((size_t *)input)[i];
            if (input_size_t > INT_MAX)
                error("usize cannot be greater than INT_MAX");
            INTEGER(result)
            [i] = (int)input_size_t;
        }
        UNPROTECT(1);
    }

    else if (str_equal(c_origin, "bool"))
    {
        result = PROTECT(allocVector(LGLSXP, len));
        for (int i = 0; i < len; i++)
        {
            LOGICAL(result)
            [i] = ((bool *)input)[i];
        }
        UNPROTECT(1);
    }
    else if (str_equal(c_origin, "ExtrinsicObject"))
    {
        if (len == 1)
            result = extrinsic_object_to_sexp((ExtrinsicObject *)input);
        else
        {
            result = PROTECT(allocVector(VECSXP, len));
            for (int i = 0; i < len; i++)
                SET_VECTOR_ELT(result, i, extrinsic_object_to_sexp(((ExtrinsicObject *)input) + i));
            UNPROTECT(1);
        }
    }
    else
        error_unknown_type("voidptr_to_sexp unknown type:", c_origin);

    UNPROTECT(1);
    return result;
}

SEXP slice_to_tuple(FfiSlice *raw, SEXP type_name)
{
    PROTECT(type_name);
    SEXP args = get_args(type_name);
    size_t len = LENGTH(args);
    SEXP result = PROTECT(allocVector(VECSXP, len));

    for (size_t i = 0; i < len; i++)
        SET_VECTOR_ELT(result, i, voidptr_to_sexp(((void **)raw->ptr)[i], VECTOR_ELT(args, i), 1));
    UNPROTECT(2);
    return result;
}

SEXP slice_to_sexp(FfiSlice *raw, SEXP type_name)
{
    const char *c_origin = sexp_to_charptr(get_origin(type_name));

    SEXP result;

    if (str_equal(c_origin, "Vec"))
        result = slice_to_vector(raw, type_name);

    else if (str_equal(c_origin, "BitVector"))
        result = slice_to_bitvector(raw, type_name);

    else if (str_equal(c_origin, "HashMap"))
        result = slice_to_hashmap(raw, type_name);

    else if (str_equal(c_origin, "Option"))
    {
        if (raw->len == 0)
            result = R_NilValue;
        else
            result = slice_to_sexp(raw, VECTOR_ELT(get_args(type_name), 0));
    }

    else if (str_equal(c_origin, "Tuple"))
        result = slice_to_tuple(raw, type_name);

    else if (is_in(c_origin, ATOM_TYPES))
        result = slice_to_scalar(raw, type_name);

    else if (str_equal(c_origin, "ExtrinsicObject"))
        result = slice_to_scalar(raw, type_name);

    else
        error_unknown_type("slice_to_sexp unknown type:", c_origin);

    return result;
}

/* End exact, unedited upstream decoder functions. */
static SEXP unexpected(const char *kind) {
    fprintf(stderr, "unexpected %s branch\n", kind);
    exit(3);
}
static SEXP slice_to_vector(FfiSlice *raw, SEXP ty) {
    (void)raw;(void)ty;return unexpected("Vec");
}
static SEXP slice_to_bitvector(FfiSlice *raw, SEXP ty) {
    (void)raw;(void)ty;return unexpected("BitVector");
}
static SEXP slice_to_hashmap(FfiSlice *raw, SEXP ty) {
    (void)raw;(void)ty;return unexpected("HashMap");
}
static SEXP slice_to_scalar(FfiSlice *raw, SEXP ty) {
    (void)raw;(void)ty;return unexpected("scalar");
}
static SEXP make_type(const char *origin, SEXP args) {
    SEXP t=allocVector(VECSXP, 0);
    t->origin=mkChar(origin);
    t->args=args;
    return t;
}
static SEXP args1(SEXP first) {
    SEXP x=allocVector(VECSXP, 1);
    SET_VECTOR_ELT(x,0,first);
    return x;
}
static SEXP args2(SEXP first, SEXP second) {
    SEXP x=allocVector(VECSXP, 2);
    SET_VECTOR_ELT(x,0,first);
    SET_VECTOR_ELT(x,1,second);
    return x;
}
static int expect_error(const char *case_name, FfiSlice *sl, SEXP ty, const char *expected) {
    last_error[0]=0;
    if (setjmp(error_target)==0) {
        SEXP result=slice_to_sexp(sl, ty);
        (void)result;
        fprintf(stderr,"%s: unexpectedly decoded\n",case_name);
        return 1;
    }
    if (strcmp(last_error,expected)!=0) {
        fprintf(stderr,"%s: unexpected error: %s\n",case_name,last_error);
        return 1;
    }
    printf("EXPECTED_ERROR %s: %s\n",case_name,last_error);
    return 0;
}
int main(void) {
    int failures=0;
    double a=3.5,b=0.125;
    int opaque=5;
    void *data[2]={&a,&b};
    FfiSlice sl={data,2};
    SEXP f64=make_type("f64",NULL);
    SEXP pair=make_type("Tuple",args2(f64,f64));

    if (setjmp(error_target)!=0) {
        fprintf(stderr, "unexpected baseline failure: %s\n",last_error);
        return 2;
    }
    SEXP result=slice_to_sexp(&sl,pair);
    if (LENGTH(result)!=2 || REAL(VECTOR_ELT(result,0))[0]!=3.5
        || REAL(VECTOR_ELT(result,1))[0]!=0.125) {
        fputs("baseline (f64,f64) tuple decode failed\n",stderr);
        failures++;
    } else puts("OK primitive_tuple");

    data[0]=&opaque;data[1]=&b;
    pair=make_type("Tuple",args2(make_type("PrivacyProfile",NULL),f64));
    failures+=expect_error("privacy_profile_tuple",&sl,pair,
                           "voidptr_to_sexp unknown type: PrivacyProfile");

    data[0]=&a;data[1]=&opaque;
    pair=make_type("Tuple",args2(f64,make_type("AnyObject",NULL)));
    SEXP some=make_type("Option",args1(pair));
    failures+=expect_error("private_candidate_some",&sl,some,
                           "voidptr_to_sexp unknown type: AnyObject");

    FfiSlice none={NULL,0};
    if (setjmp(error_target)!=0) {
        fprintf(stderr,"unexpected None error: %s\n",last_error);
        return 2;
    }
    if (slice_to_sexp(&none,some)!=R_NilValue) {
        fputs("None did not decode as nil\n",stderr);
        failures++;
    } else puts("OK private_candidate_none");
    return failures ? 1 : 0;
}
