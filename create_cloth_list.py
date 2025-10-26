import argparse
from pathlib import Path
from typing import Union, Optional # 組み込み型ではないため、Python 3.9/3.10でも必要

from PIL import Image, ImageDraw, ImageFont
from fpdf import FPDF
from fpdf.enums import Align

# A4サイズ（ポイント単位、1pt = 1/72インチ）
A4_WIDTH_PT = 595.28
A4_HEIGHT_PT = 841.89
MARGIN_PT = 30
DPI = 300
PT_PER_INCH = 72
SCALE_FACTOR = DPI / PT_PER_INCH


def find_png_files(input_dir: Path) -> list[Path]:
    """
    指定されたフォルダからPNGファイルを見つけ、ファイル名でソートします。

    Args:
        input_dir: PNGファイルを検索するディレクトリのパス。

    Returns:
        見つかったPNGファイルのパスのリスト（ファイル名でソート済み）。
    """
    if not input_dir.is_dir():
        raise FileNotFoundError(f"入力ディレクトリが見つかりません: {input_dir}")

    # *.png で検索し、ファイル名（パスのstem）でソート
    png_files = sorted(
        list(input_dir.glob("*.png")),
        key=lambda p: p.stem
    )
    return png_files


def combine_images_to_page(
    image_paths: list[Path],
    rows: int,
    cols: int,
    start_index: int = 0,
    padding: int = 5,
    font_size: int = 10,
) -> Image.Image:
    """
    複数の画像を縦N横Mに並べて1枚の画像（ページ）として結合します。
    画像には順番を示す番号を付けます。

    Args:
        image_paths: ページに配置するPNGファイルのパスのリスト。
        rows: 縦の画像数（行）。
        cols: 横の画像数（列）。
        start_index: このページの画像リストの開始番号

    Returns:
        結合されたページを表すPIL Imageオブジェクト。
    """
    # ページ全体のサイズ (A4サイズ - マージン)
    page_width_pt = int(A4_WIDTH_PT - 2 * MARGIN_PT)
    page_height_pt = int(A4_HEIGHT_PT - 2 * MARGIN_PT)

    page_width_px = int(page_width_pt * SCALE_FACTOR)
    page_height_px = int(page_height_pt * SCALE_FACTOR)

    # 各画像の最大幅と高さ
    img_max_width = page_width_px // cols
    img_max_height = page_height_px // rows

    # 新しいページ画像を作成
    page_image = Image.new("RGB", (page_width_px, page_height_px), "white")
    draw = ImageDraw.Draw(page_image)

    # フォントの設定（必要に応じて調整）
    font_size_px = int(font_size * SCALE_FACTOR)
    font_candidates = [
        "Helvetica.ttf",
        "Arial.ttf",
        "arial.ttf",
        "TImes New Roman.ttf",
        "DejaVuSans.ttf",
    ]

    font = None
    for font_name in font_candidates:
        try:
            font = ImageFont.truetype(font_name, font_size_px)
            break
        except IOError:
            continue

    if font is None:
        raise ValueError(f"No font found.")

    for i, path in enumerate(image_paths):
        img = Image.open(path)
        # 画像のアスペクト比を維持しつつ、最大サイズに合わせてリサイズ
        img_width, img_height = img.size

        scale_w = img_max_width / img_width
        scale_h = img_max_height / img_height
        scale = min(scale_w, scale_h, 1.0)

        new_width = int(img_width * scale)
        new_height = int(img_height * scale)

        if new_width != img_width or new_height != img_height:
            img = img.resize((new_width, new_height), Image.LANCZOS)

        # グリッド内の位置を計算
        idx_in_page = i % (rows * cols)
        row = idx_in_page // cols
        col = idx_in_page % cols

        # 画像の左上座標
        x_start = col * img_max_width
        y_start = row * img_max_height

        # グリッドの中心に配置
        x_center = x_start + (img_max_width - new_width) // 2
        y_center = y_start + (img_max_height - new_height) // 2

        page_image.paste(img, (x_center, y_center))

        # 番号を描画（画像の上、左上隅近くに）
        number = start_index + i + 1
        text = f"({number})"

        padding_scale = int(padding * SCALE_FACTOR)
        text_x = x_center + padding_scale
        text_y = y_center + padding_scale

        text_bbox = draw.textbbox((text_x, text_y), text, font=font)

        # text_width = text_bbox[2] - text_bbox[0]
        # text_height = text_bbox[3] - text_bbox[1]

        bg_padding = int(2 * SCALE_FACTOR)
        bg_rect = [
            text_bbox[0] - bg_padding,
            text_bbox[1] - bg_padding,
            text_bbox[2] + bg_padding,
            text_bbox[3] + bg_padding,
        ]
        draw.rectangle(bg_rect, fill=(0, 0, 0))

        draw.text((text_x, text_y), text, fill=(255, 255, 255), font=font)

    return page_image


def create_pdf_from_images(
    image_list: list[Path],
    output_pdf_path: Path,
    rows: int,
    cols: int
) -> None:
    """
    PNGファイルのリストを縦N横MでA4サイズのPDFに出力します。

    Args:
        image_list: PDFに含めるすべてのPNGファイルのパスのリスト。
        output_pdf_path: 出力するPDFファイルのパス。
        rows: 1ページあたりの縦の画像数。
        cols: 1ページあたりの横の画像数。
    """
    images_per_page = rows * cols
    
    # fpdf2 のインスタンスを作成
    pdf = FPDF(unit="pt", format="A4")
    
    # ページサイズ（ポイント単位）
    page_width = A4_WIDTH_PT
    page_height = A4_HEIGHT_PT
    
    # マージン付きの画像領域サイズ
    content_width = page_width - 2 * MARGIN_PT
    content_height = page_height - 2 * MARGIN_PT
    
    # 一時保存用のディレクトリ
    temp_dir = output_pdf_path.parent / "temp_page_images"
    # ファイルが見つからない例外が発生しないよう、明示的にディレクトリ作成を試みる
    try:
        temp_dir.mkdir(exist_ok=True)
    except Exception as e:
        print(f"一時ディレクトリの作成に失敗しました: {e}")
        return


    for i in range(0, len(image_list), images_per_page):
        # 1ページ分の画像パスをスライス
        page_images_paths = image_list[i:i + images_per_page]
        
        # 画像を結合して1枚のページ画像を生成
        combined_page = combine_images_to_page(page_images_paths, rows, cols, start_index=i)
        
        # 一時ファイルとして保存
        temp_image_path = temp_dir / f"page_{i//images_per_page + 1}.png"
        combined_page.save(temp_image_path)
        
        # PDFにページを追加
        pdf.add_page()
        
        # 画像をPDFに追加 (左上マージンから配置)
        pdf.image(
            str(temp_image_path), 
            x=MARGIN_PT, 
            y=MARGIN_PT, 
            w=content_width, 
            h=content_height
        )

    # PDFを出力
    pdf.output(str(output_pdf_path))
    print(f"PDFが正常に出力されました: {output_pdf_path}")
    
    # 一時ファイルを削除
    for file in temp_dir.glob("*.png"):
        file.unlink()
    temp_dir.rmdir()
    print("一時ファイルを削除しました。")


def main() -> None:
    """
    メイン処理を実行します。
    コマンドライン引数を解析し、PNGファイルを検索・結合・PDF出力します。
    """
    parser = argparse.ArgumentParser(
        description="指定フォルダ内のPNG画像をソートし、縦N横MでA4 PDFに出力します。"
    )
    parser.add_argument(
        "input_dir", 
        type=str, 
        help="PNG画像を検索するフォルダのパス。"
    )
    parser.add_argument(
        "output_pdf", 
        type=str, 
        help="出力するPDFファイル名（例: output.pdf）。"
    )
    parser.add_argument(
        "--rows", 
        type=int, 
            default=4, 
        help="1ページあたりの縦の画像数 (デフォルト: 4)。"
    )
    parser.add_argument(
        "--cols", 
        type=int, 
        default=3, 
        help="1ページあたりの横の画像数 (デフォルト: 3)。"
    )

    args = parser.parse_args()

    # pathlibでパスオブジェクトに変換
    input_path = Path(args.input_dir)
    output_path = Path(args.output_pdf)
    rows = args.rows
    cols = args.cols

    if rows < 1 or cols < 1:
        print("エラー: 縦横の画像数は1以上である必要があります。")
        return

    # 1. ファイルを検索し、ソート
    png_files = find_png_files(input_path)
    
    if not png_files:
        print(f"警告: {input_path} にPNGファイルが見つかりませんでした。")
        return

    print(f"合計 {len(png_files)} 個のPNGファイルが見つかりました。")
    print(f"1ページあたり縦 {rows}、横 {cols} ({rows * cols}枚) で配置します。")
    
    # 2. PDFを作成
    create_pdf_from_images(png_files, output_path, rows, cols)


if __name__ == "__main__":
    main()
