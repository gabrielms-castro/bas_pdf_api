import os
import subprocess
import tempfile
import pymupdf

class PdfDividerStrategy:
    """
    Classe base abstrata para diferentes estratégias de divisão de PDF.
    """
    def divide_pdf(self, pdf_path, eventos, output_dir, nome_arquivo):
        raise NotImplementedError("Subclasses devem implementar o método divide_pdf.")

class GeneralPdfDivider(PdfDividerStrategy):
    """
    Divisor de PDF padrão usando PyMuPDF.
    """
    def divide_pdf(self, pdf_path, eventos, output_dir, nome_arquivo):
        doc = pymupdf.open(pdf_path)
        arquivos_gerados = []

        for evento in eventos:
            try:
                numero_evento = evento.get("numero_evento")
                pagina_inicial = evento.get("pagina_inicial") - 1
                pagina_final = evento.get("pagina_final") - 1
                data_evento = evento.get("data_evento")

                novo_pdf = pymupdf.open()
                for pagina_num in range(pagina_inicial, pagina_final + 1):
                    novo_pdf.insert_pdf(doc, from_page=pagina_num, to_page=pagina_num)

                output_pdf = os.path.join(
                    output_dir,
                    f"{nome_arquivo}_evento_{numero_evento}_pgInicial_{pagina_inicial + 1}_pgFinal_{pagina_final + 1}_{data_evento}.pdf",
                )

                novo_pdf.save(output_pdf, deflate=True)
                novo_pdf.close()
                arquivos_gerados.append(output_pdf)

            except Exception as e:
                print(f"Erro ao processar evento {evento.get('numero_evento')}: {e}")

        doc.close()
        return arquivos_gerados

class EprocPdfDivider(PdfDividerStrategy):
    """
    Divisor de PDF para o sistema EPROC usando Ghostscript.
    """
    def divide_pdf(self, pdf_path, eventos, output_dir, nome_arquivo):
        arquivos_gerados = []

        for evento in eventos:
            numero_evento = evento.get("numero_evento")
            pagina_inicial = evento.get("pagina_inicial")
            pagina_final = evento.get("pagina_final")
            data_evento = evento.get("data_evento")

            output_pdf = os.path.join(
                output_dir,
                f"{nome_arquivo}_evento_{numero_evento}_pgInicial_{pagina_inicial}_pgFinal_{pagina_final}_{data_evento}.pdf",
            )

            comando = [
                "gs",
                "-dBATCH",
                "-dNOPAUSE",
                "-sDEVICE=pdfwrite",
                f"-sPageList={pagina_inicial}-{pagina_final}",
                f"-sOutputFile={output_pdf}",
                pdf_path,
            ]

            try:
                subprocess.run(comando, check=True)
                arquivos_gerados.append(output_pdf)
            except subprocess.CalledProcessError as e:
                print(f"Erro ao processar evento {numero_evento}: {e}")

        return arquivos_gerados
