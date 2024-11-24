import os
import re
import pymupdf 
import tempfile

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser
from rest_framework import status


class ProcessorBase:
    def process(self, pdf_path):
        raise NotImplementedError("Subclasses devem implementar o método 'process'.")


class PJEProcessor(ProcessorBase):
    def process(self, pdf_path):
        texto_paginas = self.pdf_text_extract(pdf_path)
        eventos = self.pje_processor(texto_paginas)
        return self.rename_events(eventos)

    def pdf_text_extract(self, pdf_path):
        doc = pymupdf.open(pdf_path)
        texto_paginas = {}
        for pagina_num in range(len(doc)):
            pagina = doc.load_page(pagina_num)
            texto_paginas[pagina_num + 1] = pagina.get_text()
        return texto_paginas

    def rename_events(self, events):
        numero_evento = 0
        for event in events:
            numero_evento += 1
            event["numero_evento"] = numero_evento
        return events

    def pje_processor(self, texto_paginas):
        eventos = []
        evento_atual = None
        total_paginas = len(texto_paginas)

        for pagina_num, texto in texto_paginas.items():
            match = re.search(r"Número do documento:\s*(\d+)", texto)
            if match:
                numero_evento = match.group(1)

                if evento_atual and evento_atual["numero_evento"] != numero_evento:
                    evento_atual["pagina_final"] = pagina_num - 1
                    eventos.append(evento_atual)
                    evento_atual = None

                if not evento_atual:
                    evento_atual = {
                        "numero_evento": numero_evento,
                        "pagina_inicial": pagina_num,
                        "pagina_final": None,
                    }
            elif evento_atual:
                evento_atual["pagina_final"] = pagina_num

        if evento_atual:
            evento_atual["pagina_final"] = total_paginas
            eventos.append(evento_atual)

        return eventos


class EPROCProcessor(ProcessorBase):
    def process(self, pdf_path):
        texto_paginas = self.pdf_text_extract(pdf_path)
        return self.eproc_processor(texto_paginas)

    def pdf_text_extract(self, pdf_path):
        doc = pymupdf.open(pdf_path)
        texto_paginas = {}
        for pagina_num in range(len(doc)):
            pagina = doc.load_page(pagina_num)
            texto_paginas[pagina_num + 1] = pagina.get_text()
        return texto_paginas

    def eproc_processor(self, texto_paginas):
        eventos = []
        evento_atual = None

        for pagina_num, texto in texto_paginas.items():
            if "PÁGINA DE SEPARAÇÃO" in texto:
                if evento_atual:
                    evento_atual["pagina_final"] = pagina_num - 1
                    eventos.append(evento_atual)

                numero_evento = re.search(r"Evento (\d+)", texto)
                evento_atual = {
                    "numero_evento": int(numero_evento.group(1)) if numero_evento else None,
                    "pagina_inicial": pagina_num,
                    "pagina_final": None,
                }
            elif evento_atual:
                evento_atual["pagina_final"] = pagina_num

        if evento_atual:
            eventos.append(evento_atual)

        return eventos


class ProcessorFactory:
    def get_processor(self, sistema_processual):
        if sistema_processual == "pje":
            return PJEProcessor()
        elif sistema_processual == "eproc":
            return EPROCProcessor()
        else:
            raise ValueError("Sistema processual inválido.")


class ProcessarPDFView(APIView):
    parser_classes = [MultiPartParser]
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        pdf_file = request.FILES.get('file')
        if not pdf_file:
            return Response({"error": "Nenhum arquivo enviado."}, status=status.HTTP_400_BAD_REQUEST)

        sistema_processual = request.data.get('sistema_processual')
        if not sistema_processual:
            return Response({"error": "Sistema processual não especificado."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_pdf:
                for chunk in pdf_file.chunks():
                    temp_pdf.write(chunk)

                temp_pdf_path = temp_pdf.name

            processor = ProcessorFactory().get_processor(sistema_processual)
            resultado = processor.process(temp_pdf_path)

            return Response(resultado, status=status.HTTP_200_OK)

        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            if os.path.exists(temp_pdf_path):
                os.remove(temp_pdf_path)
