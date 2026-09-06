/*
 * ebharness - headless libretro runner for automated SNES ROM testing.
 *
 * usage: ebharness <core.so> <rom.sfc> <script.txt> <outdir> [ld65.map]   (or EBH_MAP=file)
 * Addresses in peek/poke/waitmem may be symbol names from the map, optionally with +offset.
 *
 * Script commands (one per line, '#' comments):
 *   run N                 run N frames with current held buttons
 *   press BTNS N          hold BTNS for N frames, then release (BTNS: a,b,x,y,l,r,start,select,up,down,left,right, '+'-joined)
 *   hold BTNS             set held buttons (persist until 'release')
 *   release               clear held buttons
 *   shot NAME             write NAME.png screenshot of last frame into outdir
 *   peek ADDR LEN         print LEN bytes of WRAM at offset ADDR (hex, 0..0x1FFFF, i.e. $7E0000-based)
 *   poke ADDR B0 B1 ...   write bytes into WRAM
 *   waitmem ADDR VAL MAX  run until WRAM[ADDR]==VAL (8-bit), at most MAX frames; prints frames taken
 *   waitmem16 ADDR VAL MAX  same, 16-bit little endian
 *   save NAME             serialize state to outdir/NAME.st
 *   load NAME             unserialize state from outdir/NAME.st
 *   echo TEXT             print TEXT
 *   fps                   print frame counter
 *   inputlog ON|OFF       (reserved)
 *
 * WRAM offsets are relative to $7E0000 (so $7E1234 -> 0x1234, $7F0000 -> 0x10000).
 */
#include <stdio.h>
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>
#include <dlfcn.h>
#include <png.h>
#include "libretro.h"

static void *core;
static retro_video_refresh_t core_video;
static uint16_t framebuf[512 * 480];
static unsigned fb_w, fb_h;
static unsigned pixfmt = RETRO_PIXEL_FORMAT_0RGB1555;
static uint16_t held = 0;       /* bitmask of RETRO_DEVICE_ID_JOYPAD_* */
static unsigned long frame_no = 0;
static uint8_t *wram; static size_t wram_size;
static const char *outdir = ".";

#define BTN(id) (1u << (id))

static void log_cb(enum retro_log_level level, const char *fmt, ...) {
    (void)level;
    va_list ap; va_start(ap, fmt);
    if (getenv("EBH_VERBOSE")) vfprintf(stderr, fmt, ap);
    va_end(ap);
}

static bool env_cb(unsigned cmd, void *data) {
    switch (cmd) {
    case RETRO_ENVIRONMENT_SET_PIXEL_FORMAT:
        pixfmt = *(enum retro_pixel_format *)data;
        return true;
    case RETRO_ENVIRONMENT_GET_SYSTEM_DIRECTORY:
    case RETRO_ENVIRONMENT_GET_SAVE_DIRECTORY:
    case RETRO_ENVIRONMENT_GET_CORE_ASSETS_DIRECTORY:
        *(const char **)data = outdir;
        return true;
    case RETRO_ENVIRONMENT_GET_LOG_INTERFACE: {
        struct retro_log_callback *cb = (struct retro_log_callback *)data;
        cb->log = log_cb;
        return true;
    }
    case RETRO_ENVIRONMENT_GET_CAN_DUPE:
        *(bool *)data = true;
        return true;
    case RETRO_ENVIRONMENT_GET_VARIABLE: {
        struct retro_variable *var = (struct retro_variable *)data;
        /* keep default rendering; disable overclock etc. */
        var->value = NULL;
        return false;
    }
    case RETRO_ENVIRONMENT_SET_VARIABLES:
    case RETRO_ENVIRONMENT_SET_CORE_OPTIONS:
    case RETRO_ENVIRONMENT_SET_CORE_OPTIONS_INTL:
    case RETRO_ENVIRONMENT_SET_SUPPORT_ACHIEVEMENTS:
    case RETRO_ENVIRONMENT_SET_INPUT_DESCRIPTORS:
    case RETRO_ENVIRONMENT_SET_CONTROLLER_INFO:
        return true;
    case RETRO_ENVIRONMENT_SET_MEMORY_MAPS: {
        const struct retro_memory_map *m = (const struct retro_memory_map *)data;
        for (unsigned i = 0; i < m->num_descriptors; i++) {
            const struct retro_memory_descriptor *d = &m->descriptors[i];
            if (d->ptr && d->start == 0x7E0000 && d->len >= 0x10000) {
                wram = (uint8_t *)d->ptr + d->offset; wram_size = d->len;
                fprintf(stderr, "wram from memory map: %zu bytes\n", wram_size);
            }
        }
        return true;
    }
    case RETRO_ENVIRONMENT_SET_GEOMETRY:
    case RETRO_ENVIRONMENT_SET_SUBSYSTEM_INFO:
    case RETRO_ENVIRONMENT_SET_SERIALIZATION_QUIRKS:
        return true;
    case RETRO_ENVIRONMENT_GET_VARIABLE_UPDATE:
        *(bool *)data = false;
        return true;
    case RETRO_ENVIRONMENT_GET_CORE_OPTIONS_VERSION:
        *(unsigned *)data = 2;
        return true;
    case RETRO_ENVIRONMENT_GET_LANGUAGE:
        *(unsigned *)data = RETRO_LANGUAGE_ENGLISH;
        return true;
    default:
        return false;
    }
}

static void video_cb(const void *data, unsigned width, unsigned height, size_t pitch) {
    if (!data) return; /* dupe frame */
    fb_w = width; fb_h = height;
    for (unsigned y = 0; y < height && y < 480; y++) {
        if (pixfmt == RETRO_PIXEL_FORMAT_XRGB8888) {
            const uint32_t *src = (const uint32_t *)((const uint8_t *)data + y * pitch);
            for (unsigned x = 0; x < width && x < 512; x++) {
                uint32_t p = src[x];
                framebuf[y * 512 + x] = (uint16_t)((((p >> 16) & 0xFF) >> 3) << 11 | (((p >> 8) & 0xFF) >> 2) << 5 | ((p & 0xFF) >> 3));
            }
        } else {
            const uint16_t *src = (const uint16_t *)((const uint8_t *)data + y * pitch);
            memcpy(&framebuf[y * 512], src, width * 2);
        }
    }
}

static void audio_sample_cb(int16_t l, int16_t r) { (void)l; (void)r; }
static size_t audio_batch_cb(const int16_t *d, size_t frames) { (void)d; return frames; }
static void input_poll_cb(void) {}
static int16_t input_state_cb(unsigned port, unsigned device, unsigned index, unsigned id) {
    (void)index;
    if (port != 0) return 0;
    if (device == RETRO_DEVICE_JOYPAD) {
        if (id == RETRO_DEVICE_ID_JOYPAD_MASK) return (int16_t)held;
        if (id < 16) return (held >> id) & 1;
    }
    return 0;
}

/* ---- core function pointers ---- */
#define LOAD_SYM(name) name##_p = (typeof(name##_p))dlsym(core, #name); if (!name##_p) { fprintf(stderr, "missing symbol %s\n", #name); exit(1); }
static void (*retro_set_environment_p)(retro_environment_t);
static void (*retro_set_video_refresh_p)(retro_video_refresh_t);
static void (*retro_set_audio_sample_p)(retro_audio_sample_t);
static void (*retro_set_audio_sample_batch_p)(retro_audio_sample_batch_t);
static void (*retro_set_input_poll_p)(retro_input_poll_t);
static void (*retro_set_input_state_p)(retro_input_state_t);
static void (*retro_init_p)(void);
static void (*retro_deinit_p)(void);
static bool (*retro_load_game_p)(const struct retro_game_info *);
static void (*retro_run_p)(void);
static size_t (*retro_serialize_size_p)(void);
static bool (*retro_serialize_p)(void *, size_t);
static bool (*retro_unserialize_p)(const void *, size_t);
static void *(*retro_get_memory_data_p)(unsigned);
static void (*ebh_get_cpu_p)(uint32_t *);   /* optional: only the patched snes9x core exports it */
static size_t (*retro_get_memory_size_p)(unsigned);
static void (*retro_get_system_av_info_p)(struct retro_system_av_info *);


/* ---- symbol table from ld65 map (Exports list), WRAM symbols only ---- */
struct sym { char name[64]; unsigned long addr; };
static struct sym *syms; static size_t nsyms, capsyms;
static void load_map(const char *path) {
    FILE *f = fopen(path, "r"); if (!f) { perror(path); return; }
    char line[512]; bool in_exports = false;
    while (fgets(line, sizeof line, f)) {
        if (strstr(line, "Exports list by name")) { in_exports = true; continue; }
        if (strstr(line, "Imports list")) break;
        if (!in_exports) continue;
        char *p = line;
        while (*p) {
            char name[64]; unsigned long addr; char type[8]; int consumed = 0;
            if (sscanf(p, "%63s %lx %7s%n", name, &addr, type, &consumed) != 3) break;
            if (type[0] == 'R' || type[0] == 'L') {
                if (nsyms == capsyms) { capsyms = capsyms ? capsyms * 2 : 4096; syms = realloc(syms, capsyms * sizeof *syms); }
                strncpy(syms[nsyms].name, name, 63); syms[nsyms].name[63] = 0; syms[nsyms].addr = addr; nsyms++;
            }
            p += consumed;
        }
    }
    fclose(f);
    fprintf(stderr, "loaded %zu symbols from %s\n", nsyms, path);
}
/* resolve "NAME", "NAME+0x10", or numeric; WRAM addresses ($7Exxxx/$7Fxxxx) are mapped to 0..0x1FFFF */
static unsigned long resolve(const char *s) {
    char buf[256]; strncpy(buf, s, 255); buf[255] = 0;
    long off = 0; char *plus = strchr(buf, '+');
    if (plus) { off = strtol(plus + 1, NULL, 0); *plus = 0; }
    unsigned long base;
    if ((buf[0] >= '0' && buf[0] <= '9')) base = strtoul(buf, NULL, 0);
    else {
        size_t i; for (i = 0; i < nsyms; i++) if (!strcmp(syms[i].name, buf)) break;
        if (i == nsyms) { fprintf(stderr, "unknown symbol %s\n", buf); return 0; }
        base = syms[i].addr;
    }
    if (base >= 0x7E0000 && base <= 0x7FFFFF) base -= 0x7E0000;
    return base + off;
}


static unsigned long parse_num(const char *s);
/* ---- automated dodging player for playtests ------------------------------ */
#define BH_TYPE_BLUE_C (7)
#define BH_TYPE_ORANGE_C (8)
/* nearest ROM/RAM symbol at or below addr, as "NAME+off" */
static const char *sym_for(unsigned long addr) {
    static char buf[96]; size_t best = (size_t)-1;
    if (addr < 0x400000 && (addr & 0xFFFF) >= 0x8000) addr |= 0xC00000;   /* bank 00-3F mirror of C0-FF */
    for (size_t i = 0; i < nsyms; i++)
        if (syms[i].addr <= addr && (best == (size_t)-1 || syms[i].addr > syms[best].addr) && addr - syms[i].addr < 0x4000) best = i;
    if (best == (size_t)-1) snprintf(buf, sizeof buf, "?");
    else snprintf(buf, sizeof buf, "%s+%lx", syms[best].name, addr - syms[best].addr);
    return buf;
}
static long sym_addr(const char *name) { char b[64]; snprintf(b, sizeof b, "%s", name); return (long)parse_num(b); }
static int16_t rd16(unsigned long a) { return (int16_t)(wram[a] | (wram[a + 1] << 8)); }
/* returns the best move (dx,dy in {-2,0,2}) for this frame */
static void dodge_pick(unsigned long dp, unsigned long bul, int *odx, int *ody) {
    int hx = rd16(dp + 0x12), hy = rd16(dp + 0x14);
    int x0 = rd16(dp + 0x16), y0 = rd16(dp + 0x18), x1 = rd16(dp + 0x1A), y1 = rd16(dp + 0x1C);
    int cx = (x0 + x1) / 2 - 8, cy = (y0 + y1) / 2 - 8;
    double best = -1e9; int bdx = 0, bdy = 0;
    static const int mv[9][2] = {{0,0},{-2,0},{2,0},{0,-2},{0,2},{-2,-2},{2,-2},{-2,2},{2,2}};
    for (int m = 0; m < 9; m++) {
        int dx = mv[m][0], dy = mv[m][1];
        double score = 1e9;
        for (int t = 0; t < 20; t++) {
            int px = hx + dx * (t + 1), py = hy + dy * (t + 1);
            if (px < x0 + 1) px = x0 + 1; if (px > x1 - 17) px = x1 - 17;
            if (py < y0 + 1) py = y0 + 1; if (py > y1 - 17) py = y1 - 17;
            int hcx = px + 8, hcy = py + 8;
            for (int i = 0; i < 32; i++) {
                unsigned long r = bul + i * 16;
                int type = wram[r + 8]; if (!type) continue;
                int big = wram[r + 11] & 0x80;
                int moving = (dx || dy);
                if (type == BH_TYPE_ORANGE_C && moving) continue;   /* orange only hurts a still heart */
                if (type == BH_TYPE_BLUE_C && !moving) continue;    /* blue only hurts a moving heart */
                double bx = (rd16(r + 0) + rd16(r + 4) * t + (big ? 16 : 8) * 16) / 16.0;
                double by = (rd16(r + 2) + rd16(r + 6) * t + (big ? 16 : 8) * 16) / 16.0;
                double hw = wram[r + 14] + 1.0, hh = wram[r + 15] + 1.0;
                double ddx = (bx - hcx) / hw, ddy = (by - hcy) / hh;
                double d = ddx < 0 ? -ddx : ddx; double e = ddy < 0 ? -ddy : ddy; if (e > d) d = e;
                d -= t * 0.03;                     /* nearer in time = more urgent */
                if (d < score) score = d;
            }
        }
        /* prefer the middle of the box a little, and staying still very slightly */
        int fx = hx + dx * 6, fy = hy + dy * 6;
        double cen = ((fx - cx) * (fx - cx) + (fy - cy) * (fy - cy)) / 20000.0;
        score = (score > 3.0 ? 3.0 : score) - cen - (m ? 0.001 : 0);
        if (score > best) { best = score; bdx = dx; bdy = dy; }
    }
    *odx = bdx; *ody = bdy;
}

static void write_png(const char *name) {
    char path[1024];
    snprintf(path, sizeof path, "%s/%s.png", outdir, name);
    FILE *f = fopen(path, "wb");
    if (!f) { perror(path); return; }
    png_structp png = png_create_write_struct(PNG_LIBPNG_VER_STRING, NULL, NULL, NULL);
    png_infop info = png_create_info_struct(png);
    png_init_io(png, f);
    png_set_IHDR(png, info, fb_w, fb_h, 8, PNG_COLOR_TYPE_RGB, PNG_INTERLACE_NONE, PNG_COMPRESSION_TYPE_DEFAULT, PNG_FILTER_TYPE_DEFAULT);
    png_write_info(png, info);
    uint8_t *row = malloc(fb_w * 3);
    for (unsigned y = 0; y < fb_h; y++) {
        for (unsigned x = 0; x < fb_w; x++) {
            uint16_t p = framebuf[y * 512 + x];
            unsigned r, g, b;
            if (pixfmt == RETRO_PIXEL_FORMAT_RGB565 || pixfmt == RETRO_PIXEL_FORMAT_XRGB8888) {
                r = (p >> 11) & 31; g = (p >> 5) & 63; b = p & 31;
                row[x*3] = (r << 3) | (r >> 2); row[x*3+1] = (g << 2) | (g >> 4); row[x*3+2] = (b << 3) | (b >> 2);
            } else {
                r = (p >> 10) & 31; g = (p >> 5) & 31; b = p & 31;
                row[x*3] = (r << 3) | (r >> 2); row[x*3+1] = (g << 3) | (g >> 2); row[x*3+2] = (b << 3) | (b >> 2);
            }
        }
        png_write_row(png, row);
    }
    free(row);
    png_write_end(png, NULL);
    png_destroy_write_struct(&png, &info);
    fclose(f);
    printf("shot %s (%ux%u) frame %lu\n", path, fb_w, fb_h, frame_no);
}

static uint16_t parse_buttons(const char *s) {
    uint16_t m = 0;
    char buf[256]; strncpy(buf, s, sizeof buf - 1); buf[sizeof buf - 1] = 0;
    for (char *tok = strtok(buf, "+,"); tok; tok = strtok(NULL, "+,")) {
        if (!strcmp(tok, "a")) m |= BTN(RETRO_DEVICE_ID_JOYPAD_A);
        else if (!strcmp(tok, "b")) m |= BTN(RETRO_DEVICE_ID_JOYPAD_B);
        else if (!strcmp(tok, "x")) m |= BTN(RETRO_DEVICE_ID_JOYPAD_X);
        else if (!strcmp(tok, "y")) m |= BTN(RETRO_DEVICE_ID_JOYPAD_Y);
        else if (!strcmp(tok, "l")) m |= BTN(RETRO_DEVICE_ID_JOYPAD_L);
        else if (!strcmp(tok, "r")) m |= BTN(RETRO_DEVICE_ID_JOYPAD_R);
        else if (!strcmp(tok, "start")) m |= BTN(RETRO_DEVICE_ID_JOYPAD_START);
        else if (!strcmp(tok, "select")) m |= BTN(RETRO_DEVICE_ID_JOYPAD_SELECT);
        else if (!strcmp(tok, "up")) m |= BTN(RETRO_DEVICE_ID_JOYPAD_UP);
        else if (!strcmp(tok, "down")) m |= BTN(RETRO_DEVICE_ID_JOYPAD_DOWN);
        else if (!strcmp(tok, "left")) m |= BTN(RETRO_DEVICE_ID_JOYPAD_LEFT);
        else if (!strcmp(tok, "right")) m |= BTN(RETRO_DEVICE_ID_JOYPAD_RIGHT);
        else if (!strcmp(tok, "none")) ;
        else fprintf(stderr, "unknown button '%s'\n", tok);
    }
    return m;
}

static void run_frames(unsigned long n) {
    for (unsigned long i = 0; i < n; i++) { retro_run_p(); frame_no++; }
}

static unsigned long parse_num(const char *s) { return resolve(s); }

int main(int argc, char **argv) {
    if (argc < 5) { fprintf(stderr, "usage: %s core.so rom.sfc script.txt outdir\n", argv[0]); return 2; }
    outdir = argv[4];
    if (getenv("EBH_MAP")) load_map(getenv("EBH_MAP"));
    if (argc >= 6) load_map(argv[5]);
    core = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (!core) { fprintf(stderr, "dlopen: %s\n", dlerror()); return 1; }
    LOAD_SYM(retro_set_environment); LOAD_SYM(retro_set_video_refresh); LOAD_SYM(retro_set_audio_sample);
    LOAD_SYM(retro_set_audio_sample_batch); LOAD_SYM(retro_set_input_poll); LOAD_SYM(retro_set_input_state);
    LOAD_SYM(retro_init); LOAD_SYM(retro_deinit); LOAD_SYM(retro_load_game); LOAD_SYM(retro_run);
    LOAD_SYM(retro_serialize_size); LOAD_SYM(retro_serialize); LOAD_SYM(retro_unserialize);
    LOAD_SYM(retro_get_memory_data); LOAD_SYM(retro_get_memory_size); LOAD_SYM(retro_get_system_av_info);
    ebh_get_cpu_p = (void (*)(uint32_t *))dlsym(core, "ebh_get_cpu");

    retro_set_environment_p(env_cb);
    retro_set_video_refresh_p(video_cb);
    retro_set_audio_sample_p(audio_sample_cb);
    retro_set_audio_sample_batch_p(audio_batch_cb);
    retro_set_input_poll_p(input_poll_cb);
    retro_set_input_state_p(input_state_cb);
    retro_init_p();

    /* load ROM into memory (core needs data when need_fullpath is false; snes9x accepts data) */
    FILE *rf = fopen(argv[2], "rb");
    if (!rf) { perror(argv[2]); return 1; }
    fseek(rf, 0, SEEK_END); long rsz = ftell(rf); fseek(rf, 0, SEEK_SET);
    void *rom = malloc(rsz); if (fread(rom, 1, rsz, rf) != (size_t)rsz) { fprintf(stderr, "short read\n"); return 1; } fclose(rf);
    struct retro_game_info gi = { .path = argv[2], .data = rom, .size = rsz, .meta = NULL };
    if (!retro_load_game_p(&gi)) { fprintf(stderr, "retro_load_game failed\n"); return 1; }
    if (retro_get_memory_size_p(RETRO_MEMORY_SYSTEM_RAM) > 0) {
        wram = retro_get_memory_data_p(RETRO_MEMORY_SYSTEM_RAM);
        wram_size = retro_get_memory_size_p(RETRO_MEMORY_SYSTEM_RAM);
    }
    struct retro_system_av_info av; retro_get_system_av_info_p(&av);
    fprintf(stderr, "loaded; wram=%zu bytes, %ux%u @ %.2f fps\n", wram_size, av.geometry.base_width, av.geometry.base_height, av.timing.fps);

    FILE *sf = fopen(argv[3], "r");
    if (!sf) { perror(argv[3]); return 1; }
    char line[1024];
    int rc = 0;
    while (fgets(line, sizeof line, sf)) {
        char *p = line; while (*p == ' ' || *p == '\t') p++;
        if (*p == '#' || *p == '\n' || *p == 0) continue;
        char *nl = strchr(p, '\n'); if (nl) *nl = 0;
        char cmd[64], a1[256], a2[256], a3[256];
        int n = sscanf(p, "%63s %255s %255s %255s", cmd, a1, a2, a3);
        if (n < 1) continue;
        if (!wram_size && retro_get_memory_size_p(RETRO_MEMORY_SYSTEM_RAM) > 0) {
            wram = retro_get_memory_data_p(RETRO_MEMORY_SYSTEM_RAM);
            wram_size = retro_get_memory_size_p(RETRO_MEMORY_SYSTEM_RAM);
            fprintf(stderr, "wram (late): %zu bytes\n", wram_size);
        }
        if (!strcmp(cmd, "run")) { run_frames(parse_num(a1)); }
        else if (!strcmp(cmd, "press")) { uint16_t save = held; held |= parse_buttons(a1); run_frames(n >= 3 ? parse_num(a2) : 2); held = save; }
        else if (!strcmp(cmd, "hold")) { held = parse_buttons(a1); }
        else if (!strcmp(cmd, "release")) { held = 0; }
        else if (!strcmp(cmd, "shot")) { write_png(a1); }
        else if (!strcmp(cmd, "echo")) { printf("%s\n", p + 5); }
        else if (!strcmp(cmd, "fps")) { printf("frame %lu\n", frame_no); }
        else if (!strcmp(cmd, "peek")) {
            unsigned long addr = parse_num(a1), len = n >= 3 ? parse_num(a2) : 1;
            printf("peek %05lX:", addr);
            for (unsigned long i = 0; i < len && addr + i < wram_size; i++) printf(" %02X", wram[addr + i]);
            printf("\n");
        }
        else if (!strcmp(cmd, "poke")) {
            unsigned long addr = parse_num(a1);
            char *q = strstr(p, a1) + strlen(a1);
            unsigned long i = 0;
            for (char *tok = strtok(q, " "); tok; tok = strtok(NULL, " ")) { if (addr + i < wram_size) wram[addr + i++] = (uint8_t)strtoul(tok, NULL, 16); }
            printf("poke %05lX %lu bytes\n", addr, i);
        }
        else if (!strcmp(cmd, "waitmem") || !strcmp(cmd, "waitmem16")) {
            unsigned long addr = parse_num(a1), val = parse_num(a2), max = n >= 4 ? parse_num(a3) : 600;
            bool w16 = !strcmp(cmd, "waitmem16");
            unsigned long i;
            for (i = 0; i < max; i++) {
                unsigned long cur = w16 ? (wram[addr] | (wram[addr + 1] << 8)) : wram[addr];
                if (cur == val) break;
                run_frames(1);
            }
            printf("waitmem %05lX==%lX: %s after %lu frames (now %02X)\n", addr, val, i < max ? "ok" : "TIMEOUT", i, wram[addr]);
            if (i >= max) rc = 3;
        }
        else if (!strcmp(cmd, "wait2")) {
            /* wait2 ADDR1 VAL1 ADDR2 VAL2 [MAX]: run until both bytes match */
            char a4[256], a5[256];
            int n2 = sscanf(p, "%63s %255s %255s %255s %255s %255s", cmd, a1, a2, a3, a4, a5);
            unsigned long ad1 = parse_num(a1), v1 = parse_num(a2), ad2 = parse_num(a3), v2 = parse_num(a4), max = n2 >= 6 ? parse_num(a5) : 600;
            unsigned long i;
            for (i = 0; i < max; i++) { if (wram[ad1] == v1 && wram[ad2] == v2) break; run_frames(1); }
            printf("wait2 %05lX==%lX && %05lX==%lX: %s after %lu frames (now %02X %02X)\n", ad1, v1, ad2, v2, i < max ? "ok" : "TIMEOUT", i, wram[ad1], wram[ad2]);
            if (i >= max) rc = 3;
        }
        else if (!strcmp(cmd, "dodge")) {
            /* dodge MAXFRAMES: play the current dodge phase with the automated player until it ends */
            unsigned long dp = (unsigned long)sym_addr("BH_DP"), bul = (unsigned long)sym_addr("BH_BULLETS");
            unsigned long max = parse_num(a1), i; uint16_t save = held;
            for (i = 0; i < max; i++) {
                if (!wram[dp]) break;                 /* BH_ACTIVE */
                int dx, dy; dodge_pick(dp, bul, &dx, &dy);
                uint16_t h = 0;
                if (dx < 0) h |= BTN(RETRO_DEVICE_ID_JOYPAD_LEFT); if (dx > 0) h |= BTN(RETRO_DEVICE_ID_JOYPAD_RIGHT);
                if (dy < 0) h |= BTN(RETRO_DEVICE_ID_JOYPAD_UP);   if (dy > 0) h |= BTN(RETRO_DEVICE_ID_JOYPAD_DOWN);
                held = h; run_frames(1);
            }
            held = save;
            printf("dodge: %lu frames, hits=%u frame=%u active=%u\n", i, wram[dp + 0x0A], (unsigned)rd16(dp + 0x2A), wram[dp]);
        }
        else if (!strcmp(cmd, "sram")) {
            /* sram FILE: load a battery save (.srm) into the cartridge SRAM (do it before the game reads it, i.e. at boot) */
            FILE *f = fopen(a1, "rb"); void *sr = retro_get_memory_data_p(RETRO_MEMORY_SAVE_RAM); size_t sz = retro_get_memory_size_p(RETRO_MEMORY_SAVE_RAM);
            if (!f || !sr) { printf("sram: cannot open %s or no SRAM (%p, %zu)\n", a1, sr, sz); if (f) fclose(f); }
            else { size_t got = fread(sr, 1, sz, f); fclose(f); printf("sram: loaded %zu of %zu bytes from %s\n", got, sz, a1); }
        }
        else if (!strcmp(cmd, "peeksram")) {
            /* peeksram OFF N: hex dump of N bytes of cartridge SRAM at offset OFF */
            unsigned long off = parse_num(a1), n2 = n >= 3 ? parse_num(a2) : 16; uint8_t *sr = retro_get_memory_data_p(RETRO_MEMORY_SAVE_RAM);
            printf("sram %05lX:", off); for (unsigned long i = 0; i < n2 && sr; i++) printf(" %02X", sr[off + i]); printf("\n");
        }
        else if (!strcmp(cmd, "cpu")) {
            /* cpu: print the CPU registers (needs the patched snes9x core) */
            if (!ebh_get_cpu_p) printf("cpu: this core has no ebh_get_cpu\n");
            else { uint32_t r[8]; ebh_get_cpu_p(r);
                printf("cpu: pc=%06X (%s) s=%04X d=%04X db=%02X a=%04X x=%04X y=%04X p=%04X\n", r[0], sym_for(r[0]), r[1], r[2], r[3], r[4], r[5], r[6], r[7]); }
        }
        else if (!strcmp(cmd, "trace")) {
            /* trace N: run N frames, sampling the PC after each; print the distinct places (count, first frame) */
            unsigned long max = parse_num(a1), i; struct { uint32_t pc; unsigned long cnt, first; } seen[64]; int ns = 0;
            if (!ebh_get_cpu_p) { printf("trace: this core has no ebh_get_cpu\n"); continue; }
            for (i = 0; i < max; i++) {
                run_frames(1); uint32_t r[8]; ebh_get_cpu_p(r); int k;
                for (k = 0; k < ns; k++) if (seen[k].pc == r[0]) break;
                if (k == ns && ns < 64) { seen[ns].pc = r[0]; seen[ns].cnt = 0; seen[ns].first = i; ns++; }
                if (k < 64) seen[k].cnt++;
            }
            printf("trace %lu frames: %d distinct pcs\n", max, ns);
            for (int k = 0; k < ns; k++) printf("  pc=%06X (%s) x%lu first@%lu\n", seen[k].pc, sym_for(seen[k].pc), seen[k].cnt, seen[k].first);
            { uint32_t r[8]; ebh_get_cpu_p(r); printf("  now: pc=%06X s=%04X d=%04X db=%02X\n", r[0], r[1], r[2], r[3]); }
        }
        else if (!strcmp(cmd, "spamu")) {
            /* spamu BTNS INTERVAL MAXFRAMES ADDR VAL: press every INTERVAL frames (first press after one interval)
               until the byte at ADDR no longer equals VAL */
            char a4[256], a5[256];
            sscanf(p, "%63s %255s %255s %255s %255s %255s", cmd, a1, a2, a3, a4, a5);
            uint16_t btn = parse_buttons(a1);
            unsigned long interval = parse_num(a2), max = parse_num(a3), ad = parse_num(a4), v = parse_num(a5), i; uint16_t save = held;
            for (i = 0; i < max; i++) {
                if (wram[ad] != v) break;
                unsigned long ph = (i + 1) % interval;
                held = (ph == 0 || ph > interval - 4) ? (save | btn) : save;
                run_frames(1);
            }
            held = save;
            printf("spamu %s: %s after %lu frames (WRAM[%05lX]=%02X)\n", a1, i < max ? "changed" : "TIMEOUT", i, ad, wram[ad]);
            if (i >= max) rc = 3;
        }
        else if (!strcmp(cmd, "spamor")) {
            /* spamor BTNS INTERVAL MAXFRAMES ADDR VAL1 VAL2: press every INTERVAL frames (first press after one
               interval) until the byte at ADDR equals VAL1 or VAL2 */
            char a4[256], a5[256], a6[256];
            sscanf(p, "%63s %255s %255s %255s %255s %255s %255s", cmd, a1, a2, a3, a4, a5, a6);
            uint16_t btn = parse_buttons(a1);
            unsigned long interval = parse_num(a2), max = parse_num(a3), ad = parse_num(a4), v1 = parse_num(a5), v2 = parse_num(a6), i; uint16_t save = held;
            for (i = 0; i < max; i++) {
                if (wram[ad] == v1 || wram[ad] == v2) break;
                unsigned long ph = (i + 1) % interval;
                held = (ph == 0 || ph > interval - 4) ? (save | btn) : save;
                run_frames(1);
            }
            held = save;
            printf("spamor %s: %s after %lu frames (WRAM[%05lX]=%02X)\n", a1, i < max ? "condition met" : "TIMEOUT", i, ad, wram[ad]);
            if (i >= max) rc = 3;
        }
        else if (!strcmp(cmd, "playround")) {
            /* playround MAXFRAMES [REFILL] [HOLD]: play until a command menu (window $0F/$12) has focus: the dodge AI
               steers through dodge boxes, A is tapped every 30 frames otherwise (text, minigames, timed blocks);
               with REFILL > 0 the four party members' HP is topped up to 999 every REFILL frames */
            unsigned long max = parse_num(a1), refill = n >= 3 ? parse_num(a2) : 0, hold = n >= 4 ? parse_num(a3) : 0, i; uint16_t save = held;
            unsigned long dp = (unsigned long)sym_addr("BH_DP"), bul = (unsigned long)sym_addr("BH_BULLETS");
            unsigned long focus = (unsigned long)sym_addr("CURRENT_FOCUS_WINDOW"), bt = (unsigned long)sym_addr("BATTLERS_TABLE");
            unsigned long dodged = 0, taps = 0; unsigned dead = 0;
            /* stall detector: runs of identical frames while the game should be moving */
            uint32_t prevhash = 0; unsigned long same = 0, still_start = 0; uint32_t still_pc = 0; unsigned still_act = 0, still_mode = 0, still_fs = 0; int nstill = 0;
            for (int k = 0; k < 4; k++) { unsigned long h = bt + 78 * k + 17; if (!(wram[h] | wram[h + 1])) dead |= 1 << k; }
            for (i = 0; i < max; i++) {
                if (wram[focus] == 0x0F || wram[focus] == 0x12) break;
                if (refill && i % refill == 0) for (int k = 0; k < 4; k++) { unsigned long h = bt + 78 * k + 17;
                    if (wram[h] | wram[h + 1]) { wram[h] = 0xE7; wram[h + 1] = 3; wram[h + 2] = 0xE7; wram[h + 3] = 3; }
                    else if (!(dead & (1 << k))) { dead |= 1 << k; printf("playround: party member %d has 0 HP at frame %lu (attacker %04X, box active %u mode %u)\n", k, i,
                        (unsigned)rd16((unsigned long)sym_addr("CURRENT_ATTACKER")), wram[dp], wram[dp + 0x52]); } }
                if (wram[dp] && wram[dp + 0x52] == 0) {      /* BH_ACTIVE and BH_MODE == dodge */
                    int dx, dy; dodge_pick(dp, bul, &dx, &dy); uint16_t h = 0;
                    if (dx < 0) h |= BTN(RETRO_DEVICE_ID_JOYPAD_LEFT); if (dx > 0) h |= BTN(RETRO_DEVICE_ID_JOYPAD_RIGHT);
                    if (dy < 0) h |= BTN(RETRO_DEVICE_ID_JOYPAD_UP);   if (dy > 0) h |= BTN(RETRO_DEVICE_ID_JOYPAD_DOWN);
                    held = save | h; dodged++;
                } else if (hold) { held = save | BTN(RETRO_DEVICE_ID_JOYPAD_A); taps++; }   /* a player holding A through everything */
                else { unsigned long ph = (i + 1) % 30; held = (ph == 0 || ph > 26) ? (save | BTN(RETRO_DEVICE_ID_JOYPAD_A)) : save; if (ph == 0) taps++; }
                run_frames(1);
                { uint32_t h = 2166136261u; for (unsigned y = 0; y < fb_h; y += 4) for (unsigned x = 0; x < fb_w; x += 4) { h ^= framebuf[y * 512 + x]; h *= 16777619u; }
                  if (h == prevhash) { if (++same == 45) { still_start = i - 44; still_act = wram[dp]; still_mode = wram[dp + 0x52]; still_fs = wram[dp + 0x56];
                          if (ebh_get_cpu_p) { uint32_t r[8]; ebh_get_cpu_p(r); still_pc = r[0]; } } }
                  else { if (same >= 45 && nstill < 20) { nstill++; printf("playround: static screen for %lu frames from frame %lu (pc=%06X %s, BH_ACTIVE=%u mode=%u fight_state=%u)\n",
                          same + 1, still_start, still_pc, sym_for(still_pc), still_act, still_mode, still_fs); } same = 0; }
                  prevhash = h; }
            }
            held = save;
            if (same >= 45 && nstill < 20) printf("playround: static screen for %lu frames from frame %lu until the end (pc=%06X %s, BH_ACTIVE=%u mode=%u fight_state=%u)\n", same + 1, still_start, still_pc, sym_for(still_pc), still_act, still_mode, still_fs);
            printf("playround: %s after %lu frames (focus=%02X, %lu dodge frames, %lu taps)\n", i < max ? "menu" : "TIMEOUT", i, wram[focus], dodged, taps);
            if (i >= max) rc = 3;
        }
        else if (!strcmp(cmd, "waitle")) {
            /* waitle ADDR VAL [MAX]: run until the 16-bit word at ADDR is <= VAL */
            unsigned long addr = parse_num(a1), val = parse_num(a2), max = n >= 4 ? parse_num(a3) : 600, i;
            for (i = 0; i < max; i++) { unsigned long cur = wram[addr] | (wram[addr + 1] << 8); if (cur <= val) break; run_frames(1); }
            printf("waitle %05lX<=%lu: %s after %lu frames (now %u)\n", addr, val, i < max ? "ok" : "TIMEOUT", i, wram[addr] | (wram[addr + 1] << 8));
            if (i >= max) rc = 3;
        }
        else if (!strcmp(cmd, "spam2") || !strcmp(cmd, "spamd")) {
            /* spam2 BTNS INTERVAL MAXFRAMES ADDR1 VAL1 ADDR2 VAL2: like spam, stopping once both bytes match;
               spamd: the same with the first press delayed by one interval (a menu that is about to open is not pressed) */
            char a4[256], a5[256], a6[256], a7[256];
            int n2 = sscanf(p, "%63s %255s %255s %255s %255s %255s %255s %255s", cmd, a1, a2, a3, a4, a5, a6, a7);
            bool delayed = cmd[4] == 'd';
            uint16_t btn = parse_buttons(a1);
            unsigned long interval = parse_num(a2), max = parse_num(a3);
            unsigned long ad1 = parse_num(a4), v1 = parse_num(a5), ad2 = n2 >= 8 ? parse_num(a6) : 0, v2 = n2 >= 8 ? parse_num(a7) : 0;
            unsigned long i; uint16_t save = held;
            for (i = 0; i < max; i++) {
                if (wram[ad1] == v1 && (n2 < 8 || wram[ad2] == v2)) break;
                unsigned long ph = delayed ? (i + 1) % interval : i % interval;
                held = (delayed ? ph == 0 || ph > interval - 4 : ph < 4) ? (save | btn) : save;
                run_frames(1);
            }
            held = save;
            printf("%s %s: %s after %lu frames (WRAM[%05lX]=%02X WRAM[%05lX]=%02X)\n", cmd, a1, i < max ? "condition met" : "TIMEOUT", i, ad1, wram[ad1], ad2, wram[ad2]);
            if (i >= max) rc = 3;
        }
        else if (!strcmp(cmd, "spam")) {
            /* spam BTNS INTERVAL MAXFRAMES [ADDR VAL]: tap BTNS for 4 frames every INTERVAL frames,
               for up to MAXFRAMES frames, stopping early once WRAM[ADDR]==VAL */
            char a4[256], a5[256];
            int n2 = sscanf(p, "%63s %255s %255s %255s %255s %255s", cmd, a1, a2, a3, a4, a5);
            uint16_t btn = parse_buttons(a1);
            unsigned long interval = parse_num(a2), max = parse_num(a3);
            bool cond = n2 >= 6; unsigned long addr = cond ? parse_num(a4) : 0, val = cond ? parse_num(a5) : 0;
            unsigned long i; uint16_t save = held;
            for (i = 0; i < max; i++) {
                if (cond && wram[addr] == val) break;
                held = (i % interval) < 4 ? (save | btn) : save;
                run_frames(1);
            }
            held = save;
            if (cond) printf("spam %s: %s after %lu frames (WRAM[%05lX]=%02X)\n", a1, i < max ? "condition met" : "TIMEOUT", i, addr, wram[addr]);
            else printf("spam %s: ran %lu frames\n", a1, i);
            if (cond && i >= max) rc = 3;
        }
        else if (!strcmp(cmd, "save") || !strcmp(cmd, "load")) {
            char path[1024]; snprintf(path, sizeof path, "%s/%s.st", outdir, a1);
            size_t sz = retro_serialize_size_p();
            void *buf = malloc(sz);
            if (!strcmp(cmd, "save")) {
                if (!retro_serialize_p(buf, sz)) { fprintf(stderr, "serialize failed\n"); }
                else { FILE *f = fopen(path, "wb"); fwrite(buf, 1, sz, f); fclose(f); printf("saved %s (%zu bytes)\n", path, sz); }
            } else {
                FILE *f = fopen(path, "rb");
                if (!f) { perror(path); rc = 1; }
                else { size_t got = fread(buf, 1, sz, f); fclose(f); if (!retro_unserialize_p(buf, got)) { fprintf(stderr, "unserialize failed\n"); rc = 1; } else printf("loaded %s\n", path); }
            }
            free(buf);
        }
        else { fprintf(stderr, "unknown command: %s\n", cmd); }
        fflush(stdout);
    }
    fclose(sf);
    retro_deinit_p();
    return rc;
}
