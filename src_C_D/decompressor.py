"""
descomprimido.py - Descompressor Konami SNES
Baseado no konami_d.exe de proton (2014).

Uso (offset único):
  python descomprimido.py F8000
  python descomprimido.py 0xF8000 1          <- game_type=1

Uso (range - descomprime tudo entre dois offsets):
  python descomprimido.py F8000 FB94B
  python descomprimido.py F8000 FB94B 1      <- game_type=1
  python descomprimido.py 0 200000           <- ROM inteira

Gera: descomprimido.bin
ROM:  ISSD.sfc           (deve estar na mesma pasta)

FORMATO DE SAIDA:
  O descomprimido.bin e gerado em formato 4BPP
  Abra no YY-CHR selecionando "4BPP 8*8".
"""

import sys
import os

WINDOW_SIZE = 0x400
DATA_SIZE   = 0x20000
ROM_FILE    = "ISSD.sfc"
OUT_FILE    = "descomprimido.bin"


def parse_hex(s):
    return int(s, 16)


def snes_to_planar(data):
    """
    Converte de formato SNES intercalado para 4BPP planar (PCE/CG).

    SNES intercalado (formato nativo da ROM):
      tile[row*2]      = bp0 da linha row
      tile[row*2+1]    = bp1 da linha row
      tile[16+row*2]   = bp2 da linha row
      tile[16+row*2+1] = bp3 da linha row

    4BPP planar (formato YY-CHR SNES/PCE(CG)):
      tile[row]    = bp0 da linha row  (bytes 0-7)
      tile[8+row]  = bp1 da linha row  (bytes 8-15)
      tile[16+row] = bp2 da linha row  (bytes 16-23)
      tile[24+row] = bp3 da linha row  (bytes 24-31)

    Os indices de paleta resultantes sao identicos entre os dois formatos.
    """
    n_tiles = len(data) // 32
    out = bytearray()
    for t in range(n_tiles):
        tile = data[t*32 : t*32+32]
        converted = bytearray(32)
        for row in range(8):
            converted[row]    = tile[row*2]
            converted[8+row]  = tile[row*2+1]
            converted[16+row] = tile[16+row*2]
            converted[24+row] = tile[16+row*2+1]
        out.extend(converted)
    # preservar bytes extras alem dos tiles completos (padding de zeros)
    remainder = len(data) % 32
    if remainder:
        out.extend(data[n_tiles*32:])
    return bytes(out)


def konami_decompress(rom, offset, game_type=0):
    if offset + 2 > len(rom):
        return None, 0

    oldM1 = rom[offset]
    oldM2 = rom[offset + 1]
    comp_size = (oldM1 | (oldM2 << 8)) & 0x7FFF

    if comp_size < 4 or comp_size > 0x8000:
        return None, 0
    if offset + comp_size > len(rom):
        return None, 0

    data_start = offset + 2
    in_buf  = bytearray(DATA_SIZE)
    out_buf = bytearray(DATA_SIZE)
    win_buf = bytearray(WINDOW_SIZE)

    chunk = rom[data_start : data_start + comp_size - 2]
    in_buf[:len(chunk)] = chunk

    in_pos  = 0
    out_pos = 0
    buf_pos = 0

    def check_pos(p):
        if p >= WINDOW_SIZE:
            p -= WINDOW_SIZE
        return p

    while in_pos < comp_size - 2:
        if out_pos >= DATA_SIZE:
            break
        ctrl_byte = in_buf[in_pos]; in_pos += 1
        ctrl = ctrl_byte >> 5

        if ctrl == 0x04:                          # RAW
            cnt = ctrl_byte & 0x1F
            for _ in range(cnt):
                if in_pos >= comp_size - 2 or out_pos >= DATA_SIZE: break
                out_buf[out_pos] = in_buf[in_pos]
                win_buf[buf_pos] = in_buf[in_pos]
                out_pos += 1; buf_pos += 1; in_pos += 1
                if buf_pos >= WINDOW_SIZE:
                    buf_pos -= WINDOW_SIZE

        elif ctrl == 0x05:                        # RLE_A0
            cnt = (ctrl_byte & 0x1F) + 2
            for _ in range(cnt):
                if in_pos >= comp_size - 2 or out_pos + 1 >= DATA_SIZE: break
                ch = in_buf[in_pos]; in_pos += 1
                win_buf[buf_pos] = 0x00
                buf_pos = check_pos(buf_pos + 1)
                out_buf[out_pos] = 0x00; out_pos += 1
                win_buf[buf_pos] = ch
                buf_pos = check_pos(buf_pos + 1)
                out_buf[out_pos] = ch; out_pos += 1

        elif ctrl == 0x06:                        # RLE_C0
            cnt = (ctrl_byte & 0x1F) + 2
            if in_pos >= comp_size - 2: break
            ch  = in_buf[in_pos]; in_pos += 1
            for _ in range(cnt):
                if out_pos >= DATA_SIZE: break
                out_buf[out_pos] = ch
                win_buf[buf_pos] = ch
                out_pos += 1; buf_pos += 1
                if buf_pos >= WINDOW_SIZE:
                    buf_pos -= WINDOW_SIZE

        elif ctrl == 0x07:                        # RLE_E0
            if game_type == 0:
                cnt = (ctrl_byte & 0x1F) + 2
            else:
                if ctrl_byte != 0xFF:
                    cnt = (ctrl_byte & 0x1F) + 2
                else:
                    if in_pos >= comp_size - 2: break
                    ch  = in_buf[in_pos]; in_pos += 1
                    cnt = (ch & 0xFF) + 2
            for _ in range(cnt):
                if out_pos >= DATA_SIZE: break
                win_buf[buf_pos] = 0x00
                buf_pos += 1
                if buf_pos >= WINDOW_SIZE:
                    buf_pos -= WINDOW_SIZE
                out_buf[out_pos] = 0x00; out_pos += 1

        else:                                     # LZ
            if in_pos >= comp_size - 2: break
            lz1 = ctrl_byte
            lz2 = in_buf[in_pos]; in_pos += 1
            lz_len = (lz1 >> 2) + 2
            lz_off = ((lz1 << 8) | lz2) & 0x3FF
            lz_off = (lz_off - 0x3DF) & 0x3FF
            for _ in range(lz_len):
                if out_pos >= DATA_SIZE: break
                lz_off = check_pos(lz_off)
                ch = win_buf[lz_off]
                win_buf[buf_pos] = ch
                buf_pos = check_pos(buf_pos + 1)
                out_buf[out_pos] = ch; out_pos += 1
                lz_off = check_pos(lz_off + 1)

    return bytes(out_buf[:out_pos]), comp_size


def decompress_range(rom, start, end, game_type):
    results = []
    pos = start
    end = min(end, len(rom))
    total = end - start
    last_pct = -1

    while pos < end:
        pct = ((pos - start) * 100) // total
        if pct != last_pct and pct % 5 == 0:
            print(f"  ... {pct}%  ({pos:#010x})  blocos: {len(results)}", end="\r")
            last_pct = pct

        result, comp_size = konami_decompress(rom, pos, game_type)
        if result and len(result) >= 32:
            fim_bloco = pos + comp_size
            print(f"  Bloco -> Início: 0x{pos:06X} Fim: 0x{fim_bloco:06X} | cmp={comp_size:#06x} -> {len(result):6d} bytes ({len(result)//32} tiles)")
            results.append((pos, result))
            pos += comp_size
        else:
            pos += 2

    print()
    return results


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    os.chdir(os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__)))

    if not os.path.exists(ROM_FILE):
        print(f"ERRO: ROM não encontrada: {ROM_FILE}")
        sys.exit(1)

    rom = open(ROM_FILE, "rb").read()
    print(f"ROM: {ROM_FILE}  ({len(rom)//1024} KB)")
    print()

    arg1 = sys.argv[1]
    arg2 = sys.argv[2] if len(sys.argv) > 2 else None
    arg3 = sys.argv[3] if len(sys.argv) > 3 else None

    is_range   = False
    end_offset = 0
    game_type  = 0

    if arg2 is not None:
        try:
            val = parse_hex(arg2)
            if val > 1:
                is_range   = True
                end_offset = val
                game_type  = int(arg3, 0) if arg3 else 0
            else:
                game_type = val
        except ValueError:
            print(f"ERRO: argumento inválido: {arg2}")
            sys.exit(1)

    try:
        start_offset = parse_hex(arg1)
    except ValueError:
        print(f"ERRO: offset inválido: {arg1}")
        sys.exit(1)

    ORIG_FILE = "dadosOriginais.bin"

    if is_range:
        print(f"Modo RANGE: 0x{start_offset:X} → 0x{min(end_offset, len(rom)):X}  (game_type={game_type})")
        print("=" * 60)
        blocks = decompress_range(rom, start_offset, end_offset, game_type)

        if not blocks:
            print("Nenhum bloco válido encontrado no range.")
            sys.exit(1)

        combined        = bytearray()
        compressed_raw  = bytearray()
        total_comp_size = 0
        primeiro_offset = blocks[0][0]
        ultimo_offset_fim = primeiro_offset

        for pos, data in blocks:
            oldM1 = rom[pos]
            oldM2 = rom[pos + 1]
            comp_size = (oldM1 | (oldM2 << 8)) & 0x7FFF
            total_comp_size += comp_size
            ultimo_offset_fim = pos + comp_size
            compressed_raw.extend(rom[pos : pos + comp_size])
            # padding ate multiplo de 32
            pad = (32 - len(data) % 32) % 32
            data_padded = data + b'\x00' * pad
            combined.extend(data_padded)

        with open(OUT_FILE, "wb") as f:
            f.write(bytes(combined))
        with open(ORIG_FILE, "wb") as f:
            f.write(compressed_raw)

        print("-" * 50)
        print(f"Blocos encontrados: {len(blocks)}")
        print(f"Intervalo útil:     Início: 0x{primeiro_offset:06X} Fim: 0x{ultimo_offset_fim:06X}")
        print(f"Total comprimido:   {total_comp_size} bytes (0x{total_comp_size:X}) extraídos da ROM")
        print(f"Total descomp.:     {len(combined)} bytes ({len(combined)//32} tiles)")
        print(f"Arquivos gerados:   {OUT_FILE} e {ORIG_FILE}")
        print("-" * 50)

    else:
        print(f"Modo ÚNICO: 0x{start_offset:X}  (game_type={game_type})")
        print("=" * 60)

        result, comp_size = konami_decompress(rom, start_offset, game_type)

        if result is None:
            print(f"  FALHOU em 0x{start_offset:X} (comp_size inválido ou fora da ROM)")
            sys.exit(1)

        # padding ate multiplo de 32 (consistente com modo RANGE)
        pad = (32 - len(result) % 32) % 32
        result = result + b'\x00' * pad

        with open(OUT_FILE, "wb") as f:
            f.write(result)

        orig_data = rom[start_offset : start_offset + comp_size]
        with open(ORIG_FILE, "wb") as f:
            f.write(orig_data)

        end_offset_unico = start_offset + comp_size

        print("-" * 50)
        print(f"Endereço Lido:      Início: 0x{start_offset:06X} Fim: 0x{end_offset_unico:06X}")
        print(f"Tamanho comprimido: {comp_size} bytes (0x{comp_size:X}) na ROM")
        print(f"Total descomp.:     {len(result)} bytes ({len(result)//32} tiles)")
        print(f"Arquivos gerados:   {OUT_FILE} e {ORIG_FILE}")
        print("-" * 50)
        print()
        print("Próximos passos:")
        print(f"  1. Abra {OUT_FILE} no YY-CHR")
        print(f"  2. Edite os tiles e salve")
        print(f"  3. Execute: python compressor.py 0 1")


if __name__ == "__main__":
    main()