"""
comprimido.py - Compressor Konami SNES
Baseado no konami_c.exe de proton (2014).

Uso:
  python comprimido.py
      game_type=0
      conversao=0

  python comprimido.py <game_type>
      conversao=0

  python comprimido.py <game_type> <converter>

Onde:

game_type
    0 = jogo padrão
    1 = Strugglemeat

converter
    0 = NÃO converte (dados já estão no formato da ROM)
    1 = converte de 4BPP 8*8 para 4BPP SNES/PCE(CG) antes de comprimir

Le:   descomprimido.bin, gerado pelo descomprimido.py
Gera: recomprimido.bin
"""

import sys
import os

DATA_SIZE       = 65536
MAX_RAW_SIZE    = 31
MAX_LENGTH      = 33
MAX_ZERO_LENGTH = 257

RLE_A0 = 0xA0
RLE_C0 = 0xC0
RLE_E0 = 0xE0

IN_FILE  = "descomprimido.bin"
OUT_FILE = "recomprimido.bin"


def planar_to_snes(data):
    
    """
    Converte de formato 4BPP 8*8 para formato 4BPP SNES/PCE(CG) (planar).
    """

    n_tiles = len(data) // 32
    out = bytearray()
    for t in range(n_tiles):
        tile = data[t*32 : t*32+32]
        converted = bytearray(32)
        for row in range(8):
            converted[row*2]      = tile[row]       # bp0
            converted[row*2+1]    = tile[8+row]     # bp1
            converted[16+row*2]   = tile[16+row]    # bp2
            converted[16+row*2+1] = tile[24+row]    # bp3
        out.extend(converted)
    remainder = len(data) % 32
    if remainder:
        out.extend(data[n_tiles*32:])
    return bytes(out)


def search_rle(buf, pos, insize, game_type):
    cand_size = 0
    cand_data = 0
    cand_ar   = []
    cand_type = None

    # RLE_A0: padrao 00 XX 00 XX ...
    if (pos + 3 < insize and
            buf[pos]   == 0x00 and buf[pos+1] != 0x00 and
            buf[pos+2] == 0x00 and buf[pos+3] != 0x00):
        size = 0
        while size <= MAX_LENGTH * 2 and pos + size < insize - 1:
            if buf[pos + size] != 0x00: break
            size += 2
        val = []; rep = 1
        while rep <= size and pos + rep < insize - 1:
            if buf[pos + rep] == 0x00: break
            val.append(buf[pos + rep]); rep += 2
        rep -= 1
        ar = val[:rep // 2]
        if rep > MAX_LENGTH * 2: rep = MAX_LENGTH * 2
        if rep >= 4 and rep > cand_size:
            cand_size = rep; cand_ar = ar; cand_type = RLE_A0

    # RLE_C0: repetir byte nao-zero
    if buf[pos] != 0x00:
        size = 0
        while size <= MAX_LENGTH and pos + size < insize:
            if buf[pos + size] != buf[pos]: break
            size += 1
        if size > MAX_LENGTH: size = MAX_LENGTH
        if size >= 2 and size > cand_size:
            cand_size = size; cand_data = buf[pos]; cand_type = RLE_C0

    # RLE_E0: zeros
    if buf[pos] == 0x00:
        max_z = MAX_ZERO_LENGTH if game_type == 1 else MAX_LENGTH
        size  = 0
        while size <= max_z and pos + size < insize:
            if buf[pos + size] != 0x00: break
            size += 1
        if size > max_z: size = max_z
        if size >= 2 and size > cand_size:
            cand_size = size; cand_data = 0; cand_type = RLE_E0

    return cand_size, cand_data, cand_ar, cand_type


def search_lz(pos, buf, inputsize):
    lz_len = 0; lz_off = 0
    win = max(0, pos - 0x3DF)
    i = win
    while i < pos and i + MAX_LENGTH <= inputsize and pos < inputsize:
        if buf[i] == buf[pos]:
            match = 1
            while (i + match < inputsize and pos + match < inputsize and
                   buf[i + match] == buf[pos + match]):
                if match >= MAX_LENGTH: break
                match += 1
            if match > lz_len: lz_len = match; lz_off = i
        if lz_len >= MAX_LENGTH: lz_len = MAX_LENGTH; break
        i += 1

    # Fix Strugglemeat: removido check (lz_len + pos) < inputsize
    if lz_len >= 2:
        return lz_len, lz_off
    return 0, 0


def write_lz(out, out_pos, lz_len, lz_off):
    size    = lz_len - 2
    enc_off = (lz_off + 0x3DF) & 0x3FF
    enc_sz  = ((size << 2) & 0xFC) << 8
    ptr     = enc_off + enc_sz
    out[out_pos]     = (ptr >> 8) & 0xFF
    out[out_pos + 1] = ptr & 0xFF
    return 2

def write_rle(out, out_pos, rle_size, rle_data, rle_ar, rle_type):
    if rle_type == RLE_E0:
        if rle_size <= MAX_LENGTH:
            out[out_pos] = RLE_E0 | (rle_size - 2); return 1
        else:
            out[out_pos] = 0xFF; out[out_pos+1] = (rle_size - 2) & 0xFF; return 2
    elif rle_type == RLE_A0:
        size = (rle_size // 2) - 2
        out[out_pos] = RLE_A0 | size; w = 1
        for i in range(rle_size // 2):
            out[out_pos + w] = rle_ar[i]; w += 1
        return w
    else:  # RLE_C0
        out[out_pos]     = RLE_C0 | (rle_size - 2)
        out[out_pos + 1] = rle_data & 0xFF; return 2

def write_raw(out, out_pos, raw, raw_size):
    if raw_size == 0: return 0
    out[out_pos] = 0x80 | raw_size
    for i in range(raw_size):
        out[out_pos + 1 + i] = raw[i]
    return raw_size + 1


def konami_compress(in_data, game_type=0):
    in_size = len(in_data)
    if in_size > DATA_SIZE:
        raise ValueError(f"Arquivo muito grande: {in_size} bytes (max {DATA_SIZE})")

    buf     = bytearray(DATA_SIZE)
    out_buf = bytearray(DATA_SIZE)
    buf[:in_size] = in_data

    in_pos   = 0
    out_pos  = 2
    raw      = bytearray(MAX_RAW_SIZE)
    raw_size = 0

    while in_pos < in_size:
        lz_len = lz_off = 0
        rle_size, rle_data, rle_ar, rle_type = search_rle(buf, in_pos, in_size, game_type)

        if rle_size <= MAX_LENGTH and in_pos < in_size - 1:
            lz_len, lz_off = search_lz(in_pos, buf, in_size)

        if lz_len >= 2 and lz_len > rle_size:
            if lz_len == 2 and raw_size > 0:
                raw[raw_size] = buf[in_pos]; raw_size += 1; in_pos += 1
                if raw_size == MAX_RAW_SIZE:
                    out_pos += write_raw(out_buf, out_pos, raw, raw_size); raw_size = 0
            else:
                out_pos += write_raw(out_buf, out_pos, raw, raw_size); raw_size = 0
                out_pos += write_lz(out_buf, out_pos, lz_len, lz_off); in_pos += lz_len

        elif rle_size >= 2 and rle_size >= lz_len:
            if rle_type == RLE_E0:
                out_pos += write_raw(out_buf, out_pos, raw, raw_size); raw_size = 0
                out_pos += write_rle(out_buf, out_pos, rle_size, rle_data, rle_ar, rle_type)
                in_pos  += rle_size
            else:
                if rle_size == 2:
                    if raw_size != 0:
                        raw[raw_size] = buf[in_pos]; raw_size += 1; in_pos += 1
                        if raw_size == MAX_RAW_SIZE:
                            out_pos += write_raw(out_buf, out_pos, raw, raw_size); raw_size = 0
                    else:
                        out_pos += write_raw(out_buf, out_pos, raw, raw_size); raw_size = 0
                        out_pos += write_rle(out_buf, out_pos, rle_size, rle_data, rle_ar, rle_type)
                        in_pos  += rle_size
                else:
                    out_pos += write_raw(out_buf, out_pos, raw, raw_size); raw_size = 0
                    out_pos += write_rle(out_buf, out_pos, rle_size, rle_data, rle_ar, rle_type)
                    in_pos  += rle_size
        else:
            raw[raw_size] = buf[in_pos]; raw_size += 1; in_pos += 1
            if raw_size == MAX_RAW_SIZE:
                out_pos += write_raw(out_buf, out_pos, raw, raw_size); raw_size = 0

    out_pos += write_raw(out_buf, out_pos, raw, raw_size)

    out_buf[0] = out_pos & 0xFF
    out_buf[1] = (out_pos >> 8) & 0xFF

    return bytes(out_buf[:out_pos])


def main():
    os.chdir(os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__)))

    game_type = int(sys.argv[1], 0) if len(sys.argv) > 1 else 0
    convert_graphics = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0

    if not os.path.exists(IN_FILE):
        print(f"ERRO: {IN_FILE} nao encontrado.")
        print("Execute primeiro: python descomprimido.py <offset>")
        sys.exit(1)

    in_data = open(IN_FILE, "rb").read()

    if convert_graphics:
        print("Convertido para 4BPP SNES/PCE(CG).")
        in_data = planar_to_snes(in_data)

    compressed = konami_compress(in_data, game_type)

    with open(OUT_FILE, "wb") as f:
        f.write(compressed)

    tiles_count = len(in_data) // 32
    ratio = len(in_data) / len(compressed) if compressed else 0

    print(f"Dados lidos:    {len(in_data)} bytes ({tiles_count} tiles)")
    print(f"Comprimido:     {len(compressed)} bytes  (x{ratio:.2f})")
    print(f"Total de tiles: {tiles_count}")
    print(f"Arquivo gerado: {OUT_FILE}")
    print(f"Conversão:      {'SIM' if convert_graphics else 'NAO'}")
    print("-" * 50)

    if len(compressed) < len(in_data):
        diff = len(in_data) - len(compressed)
        print(f"STATUS: OK  (-{diff} bytes)")
    elif len(compressed) == len(in_data):
        print("STATUS: AVISO  (tamanho igual ao descomprimido)")
    else:
        diff = len(compressed) - len(in_data)
        print(f"STATUS: AVISO  (+{diff} bytes maior que o descomprimido)")
    print("-" * 50)


if __name__ == "__main__":
    main()