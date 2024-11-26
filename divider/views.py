import logging
import os
import tempfile
import traceback
import zipfile
import subprocess

import pymupdf
from django.http import FileResponse, JsonResponse
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from processor.views import ProcessorFactory

logger = logging.getLogger(__name__)


class DividerPDFView(APIView):
    parser_classes = [MultiPartParser]
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        """
        Divide o PDF enviado com base nos eventos e retorna um arquivo ZIP contendo os PDFs gerados.
        """
        pdf_file = request.FILES.get("file")
        if not pdf_file:
            return self.create_error_response("Nenhum arquivo PDF enviado.", status.HTTP_400_BAD_REQUEST)

        sistema_processual = request.data.get("sistema_processual")
        if not sistema_processual:
            return self.create_error_response("Sistema processual não especificado.", status.HTTP_400_BAD_REQUEST)

        nome_arquivo = request.data.get("nome_arquivo", pdf_file.name)
        if not nome_arquivo:
            return self.create_error_response("Nome de arquivo inválido.", status.HTTP_400_BAD_REQUEST)

        try:
            # Salva o PDF temporariamente
            temp_pdf_path = self.save_temp_file(pdf_file)

            # Compacta o PDF usando Ghostscript
            temp_pdf_optimized = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False).name
            self.reduzir_tamanho_pdf(temp_pdf_path, temp_pdf_optimized)

            # Processa o PDF para obter os eventos
            eventos = self.process_pdf(temp_pdf_optimized, sistema_processual)

            # Divide o PDF e gera os arquivos
            output_dir = tempfile.mkdtemp()
            arquivos_gerados = self.divide_pdf(temp_pdf_optimized, eventos, output_dir, nome_arquivo)

            # Compacta os PDFs em um arquivo ZIP
            zip_path = self.criar_arquivo_zip(arquivos_gerados)

            # Retorna o arquivo ZIP como resposta
            return FileResponse(open(zip_path, 'rb'), as_attachment=True, filename="arquivos_divididos.zip")

        except ValueError as e:
            return self.create_error_response(str(e), status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"Erro inesperado: {str(e)}\n{traceback.format_exc()}")
            return self.create_error_response(str(e), status.HTTP_500_INTERNAL_SERVER_ERROR)

    def reduzir_tamanho_pdf(self, input_pdf, output_pdf):
        """
        Reduz o tamanho do PDF usando Ghostscript.
        """
        command = [
            "gs",
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.4",
            "-dPDFSETTINGS=/ebook",  # Opções: /screen, /ebook, /printer, /prepress
            "-dNOPAUSE",
            "-dBATCH",
            "-sOutputFile=" + output_pdf,
            input_pdf,
        ]
        subprocess.run(command, check=True)

    def save_temp_file(self, pdf_file):
        """
        Salva um arquivo PDF temporariamente no servidor.
        """
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_pdf:
            for chunk in pdf_file.chunks():
                temp_pdf.write(chunk)
            return temp_pdf.name

    def process_pdf(self, pdf_path, sistema_processual):
        """
        Processa o PDF usando o processador adequado para o sistema processual.
        """
        processor = ProcessorFactory().get_processor(sistema_processual)
        return processor.process(pdf_path)

    def divide_pdf(self, pdf_path, eventos, output_dir, nome_arquivo):
        """
        Divide o PDF com base nos eventos fornecidos usando PyMuPDF.
        """
        doc = pymupdf.open(pdf_path)
        arquivos_gerados = []

        for evento in eventos:
            try:
                numero_evento = evento.get("numero_evento")
                pagina_inicial = evento.get("pagina_inicial") - 1
                pagina_final = evento.get("pagina_final") - 1

                # Cria um novo documento para o evento
                novo_pdf = pymupdf.open()

                for pagina_num in range(pagina_inicial, pagina_final + 1):
                    novo_pdf.insert_pdf(doc, from_page=pagina_num, to_page=pagina_num)

                output_pdf = os.path.join(
                    output_dir,
                    f"{nome_arquivo}_evento_{numero_evento}_pgInicial_{pagina_inicial + 1}_pgFinal_{pagina_final + 1}.pdf",
                )

                # Salva o novo PDF
                novo_pdf.save(output_pdf, deflate=True)
                novo_pdf.close()

                arquivos_gerados.append(output_pdf)

            except Exception as e:
                logger.error(f"Erro ao processar evento {evento.get('numero_evento')}: {e}")

        doc.close()
        return arquivos_gerados

    def criar_arquivo_zip(self, arquivos):
        """
        Cria um arquivo ZIP com os arquivos gerados.
        """
        zip_path = tempfile.NamedTemporaryFile(suffix=".zip", delete=False).name
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for arquivo in arquivos:
                zipf.write(arquivo, os.path.basename(arquivo))
        return zip_path

    def create_error_response(self, message, status_code):
        """
        Cria uma resposta de erro JSON.
        """
        return JsonResponse({"error": message}, status=status_code)
