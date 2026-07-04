# ISSD SNES Adboard Editing

Ferramentas para extrair e reinserir gráficos das placas de anúncio de **International Superstar Soccer Deluxe (SNES)** usando compressão RLE/LZ da Konami.

---

## Requisitos

- A ROM `ISSD.sfc` deve estar na **mesma pasta** dos executáveis e deve ser **sem cabeçalho** (unheadered).
- Editor de tiles: **YY-CHR**
- Editor hex para reinjeção: **HxD** ou similar

---

## Ferramentas

### `decompressor.exe`
Extrai os tiles comprimidos da ROM e gera dois arquivos:
- `descomprimido.bin` — tiles descomprimidos prontos para edição no YY-CHR
- `dadosOriginais.bin` — cópia dos bytes comprimidos originais extraídos da ROM

**Uso — offset único:**
```
decompressor.exe <offset>
decompressor.exe 0D100A
```

**Uso — range (extrai todos os blocos entre dois offsets):**
```
decompressor.exe <inicio> <fim>
decompressor.exe 0D100A 0D12AF
```

**Parâmetro `game_type` (opcional):**
```
decompressor.exe 0F8000 1
decompressor.exe 0F8000 0F8A33 1
```
Use `1` caso os dados não descomprimam corretamente com o padrão (`0`).

---

### `compressor.exe`
Lê o `descomprimido.bin` editado e gera `recomprimido.bin`, pronto para ser reinjetado na ROM.

**Uso:**
```
compressor.exe 0 1

ou, caso seja game type 1:

compressor.exe 1 1
```

---

## Fluxo completo de edição

1. Coloque `ISSD.sfc`, `decompressor.exe` e `compressor.exe` na mesma pasta
2. Execute o `decompressor.exe` com o offset desejado:
   ```
   decompressor.exe 0D100A
   ```
3. Abra `descomprimido.bin` no **YY-CHR** em modo `4BPP SNES`
4. Edite os tiles e salve o arquivo
5. Execute o `compressor.exe`:
   ```
   compressor.exe 0 1
   ```
6. Abra a ROM no **HxD** e vá até o offset original
7. Salve a ROM e teste no emulador

---

## ⚠️ Cabeçalho de tamanho (2 bytes iniciais)

No formato de compressão Konami, os **2 primeiros bytes de cada bloco** representam um valor de 16 bits em little-endian utilizado pela rotina do jogo durante a leitura do bloco comprimido que estabelece o tamanho do bloco.

```
3C 85 xx yy zz aa bb.....  →  0x853C  →  valor mascarado = 0x853C & 0x7FFF = 0x053C = 1340 bytes
```

 Exemplo de uso em parte de rotina Assembly do jogo:

```asm
$80B788:
REP #$20
LDA [$0A],Y        ; lê os 2 bytes do cabeçalho
AND #$7FFF         ; descarta o bit mais alto (flag), mantém só os 15 bits de tamanho
CLC
ADC $0000,X        ; SOMA esse valor a um offset base já carregado
STA $0F            ; resultado guardado em $0F
```

Isso indica que o cabeçalho faz parte da lógica de navegação entre blocos comprimidos na ROM, **sendo usado para determinar posições relativas durante a descompressão.**


Esse campo é estrutural dentro do formato de compressão Konami e está diretamente ligado ao mecanismo de leitura de blocos pelo jogo. Ele deve ser considerado como parte integrante do formato ao analisar ou implementar ferramentas de descompressão.

---

## Offsets das placas por seleção de time

Os offsets abaixo são endereços na ROM (.sfc) para uso direto no decompressor.exe. Este mapeamento foi construído manualmente e pode não estar completo. Se descobrir novos offsets de placas ainda não listadas, abra uma issue com o endereço e adicionarei ao guia.

---

### 🇺🇸 Placas EUA
| Início   | Fim      |
|----------|----------|
| 0D100A   | 0D12AF   |
| 0D14C1   | 0D1732   |
| 0D1732   | 0D19F8   |
| 0D517F   | 0D578F   |
| 0D578F   | 0D5A3C   |
| 0DFA90   | 0DFD84   |

---

### 🇪🇸 Placas Espanha
| Início   | Fim      |
|----------|----------|
| 0D1CAE   | 0D1F03   |
| 0D5D21   | 0D625D   |
| 0D625D   | 0D65CF   |

---

### 🇮🇹 Placas Italia
| Início   | Fim      |
|----------|----------|
| 0F8000   | 0F85EE   |
| 0F85EE   | 0F8A33   |

---

### 🇬🇧 Placas Inglaterra
| Início   | Fim      |
|----------|----------|
| 0D12AF   | 0D14C1   |
| 0DFA90   | 0DFD84   |
| 0FDA53   | 0FE022   |
| 0FE022   | 0FE35C   |

---

### 🇩🇪 Placas Alemanha
| Início   | Fim      |
|----------|----------|
| 0D625D   | 0D65CF   |
| 10156A   | 101AFD   |
| 101AFD   | 102100   |

---

### 🇧🇷 Placas Brasil
| Início   | Fim      |
|----------|----------|
| 10712B   | 10772A   |
| 10772A   | 107B7B   |
| 104C50   | 104EB4   |

---

### 🇳🇬 Placas Nigéria
| Início   | Fim      |
|----------|----------|
| 1134C5   | 113857   |
| 113857   | 11415F   |
| 11415F   | 1142FF   |
| 1142FF   | 114477   |
| 114477   | 114BB6   |
| 115EE3   | 1164C7   |

---

### 🇯🇵 Placas Japão
| Início   | Fim      |
|----------|----------|
| 0C8182   | 0C87C1   |
| 0C87C1   | 0C90A0   |

---

## Créditos

- Mapeamento dos offsets, construção dos codigos .py e .exe: **<a href="https://anderson-viana-portifolio.vercel.app/" target="blank">Anderson Viana</a>** 2026

- Compressão RLE/LZ baseada no **konami_d/konami_c** de **<a href="https://github.com/ProtonNoir/SNES-decompression-tools/tree/master/Konami" target="_blank">ProtonNoir</a>** (2014)