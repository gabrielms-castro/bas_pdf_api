import os
import zipfile
import tempfile

from django.http import FileResponse
from django.http import JsonResponse

from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from processor.views import ProcessorFactory  # Reutiliza o ProcessorFactory para obter processadores
import pymupdf


class DividerPDFView(APIView):
    parser_classes = [MultiPartParser]
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        pdf_file = request.FILES.get("file")
        if not pdf_file:
            return JsonResponse({"error": "Nenhum arquivo PDF enviado."}, status=status.HTTP_400_BAD_REQUEST)

        sistema_processual = request.data.get("sistema_processual")
        if not sistema_processual:
            return JsonResponse({"error": "Sistema processual não especificado."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Salva o PDF temporariamente
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_pdf:
                for chunk in pdf_file.chunks():
                    temp_pdf.write(chunk)

                temp_pdf_path = temp_pdf.name

            # Processa o PDF para obter os eventos
            processor = ProcessorFactory().get_processor(sistema_processual)
            eventos = processor.process(temp_pdf_path)

            # Divide o PDF e gera os arquivos
            output_dir = tempfile.mkdtemp()
            arquivos_gerados = self.divide_pdf(temp_pdf_path, eventos, output_dir)

            # Compacta os PDFs em um arquivo ZIP
            zip_path = self.criar_arquivo_zip(arquivos_gerados)

            # Retorna o arquivo ZIP como resposta
            response = FileResponse(open(zip_path, 'rb'), as_attachment=True, filename="arquivos_divididos.zip")
            return response

        except ValueError as e:
            return JsonResponse({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            # Limpa os arquivos temporários
            if os.path.exists(temp_pdf_path):
                os.remove(temp_pdf_path)

    def divide_pdf(self, pdf_path, eventos, output_dir):
        """
        Divide o PDF com base nos eventos fornecidos.

        Args:
            pdf_path (str): Caminho para o arquivo PDF.
            eventos (list): Lista de dicionários contendo "numero_evento", "pagina_inicial" e "pagina_final".
            output_dir (str): Diretório para salvar os PDFs separados.

        Returns:
            list: Lista com os caminhos dos arquivos gerados.
        """
        doc = pymupdf.open(pdf_path)
        arquivos_gerados = []

        for evento in eventos:
            numero_evento = evento.get("numero_evento")
            pagina_inicial = evento.get("pagina_inicial")
            pagina_final = evento.get("pagina_final")

            if not all([numero_evento, pagina_inicial, pagina_final]):
                continue

            novo_pdf = pymupdf.open()
            for pagina_num in range(pagina_inicial - 1, pagina_final):
                novo_pdf.insert_pdf(doc, from_page=pagina_num, to_page=pagina_num)

            output_pdf = os.path.join(output_dir, f"evento_{numero_evento}.pdf")
            novo_pdf.save(output_pdf)
            novo_pdf.close()

            arquivos_gerados.append(output_pdf)

        doc.close()
        return arquivos_gerados

    def criar_arquivo_zip(self, arquivos):
        """
        Cria um arquivo ZIP com os arquivos gerados.

        Args:
            arquivos (list): Lista de caminhos para os arquivos gerados.

        Returns:
            str: Caminho para o arquivo ZIP gerado.
        """
        zip_path = tempfile.NamedTemporaryFile(suffix=".zip", delete=False).name
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for arquivo in arquivos:
                zipf.write(arquivo, os.path.basename(arquivo))
        return zip_path
