from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser
from rest_framework import status
import pymupdf
import re


class ProcessarPDFView(APIView):
    parser_classes = [MultiPartParser]
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        # Verifica se um arquivo foi enviado
        pdf_file = request.FILES.get('file')
        if not pdf_file:
            return Response({"error": "Nenhum arquivo enviado."}, status=status.HTTP_400_BAD_REQUEST)

        sistema_processual = request.data.get('sistema_processual')
        if not sistema_processual:
            return Response({"error": "Sistema processual não especificado."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Salva o arquivo PDF em disco para leitura
            with open('temp.pdf', 'wb') as temp_pdf:
                for chunk in pdf_file.chunks():
                    temp_pdf.write(chunk)

            # Decide qual lógica aplicar com base no sistema do tribunal
            if sistema_processual == "pje":
                resultado = self.pje('temp.pdf')
                
            elif sistema_processual == "eproc":
                resultado = self.eproc('temp.pdf')
                
            else:
                return Response({"error": "Sistema rocessual inválido."}, status=status.HTTP_400_BAD_REQUEST)

            return Response(resultado, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    def pje(self, pdf_path):
        """
        Lógica para processar PDFs do PJE.
        """
        texto_paginas = self.pdf_text_extract(pdf_path)
        eventos = self.pje_processor(texto_paginas)
        eventos_renomeados = self.pje_rename_events(eventos)
        return eventos_renomeados

    def eproc(self, pdf_path):
        """
        Lógica para processar PDFs do EPROC.
        """
        texto_paginas = self.pdf_text_extract(pdf_path)
        eventos = self.eproc_processor(texto_paginas)
        return eventos

    def pdf_text_extract(self, pdf_path):
        """
        Extrai o texto de cada página do PDF.
        """
        doc = pymupdf.open(pdf_path)
        texto_paginas = {}
        for pagina_num in range(len(doc)):
            pagina = doc.load_page(pagina_num)
            texto_paginas[pagina_num + 1] = pagina.get_text()
        return texto_paginas
    
    def pje_rename_events(self, events):
        numero_evento = 0
        for event in events:
            numero_evento += 1
            event["numero_evento"] = numero_evento
        return events    
    
    def pje_processor(self, texto_paginas):
        """
        Agrupa páginas ao intervalo correspondente de cada evento pelo "Número do documento" do PJE.

        Args:
            texto_paginas (dict): Texto de cada página do PDF do PJE.

        Returns:
            list: Lista de eventos com seus intervalos de páginas.
        """
        eventos = []
        evento_atual = None
        total_paginas = len(texto_paginas)

        for pagina_num, texto in texto_paginas.items():
            # Busca o "Número do documento" na página
            match = re.search(r"Número do documento:\s*(\d+)", texto)
            if match:
                numero_evento = match.group(1)

                # Se já temos um evento em andamento e encontramos um novo
                if evento_atual and evento_atual["numero_evento"] != numero_evento:
                    evento_atual["pagina_final"] = pagina_num - 1
                    eventos.append(evento_atual)
                    evento_atual = None

                # Inicia um novo evento
                if not evento_atual:
                    evento_atual = {
                        "numero_evento": numero_evento,
                        "pagina_inicial": pagina_num,
                        "pagina_final": None,  # Será preenchido ao encontrar o próximo evento
                    }
            elif evento_atual:
                # Atualiza a página final enquanto estamos no mesmo evento
                evento_atual["pagina_final"] = pagina_num

        # Adiciona o último evento, garantindo que inclua até a última página
        if evento_atual:
            evento_atual["pagina_final"] = total_paginas
            eventos.append(evento_atual)

        return eventos

    def eproc_processor(self, texto_paginas):
        """
        Associa cada evento ao intervalo de páginas correspondente.

        Args:
            texto_paginas (dict): Texto de cada página do PDF do EPROC.

        Returns:
            list: Lista de eventos com seus intervalos de páginas.
        """
        eventos = []
        evento_atual = None

        for pagina_num, texto in texto_paginas.items():
            # Detecta uma "PÁGINA DE SEPARAÇÃO"
            if "PÁGINA DE SEPARAÇÃO" in texto:
                # Se já temos um evento em andamento, finalize-o
                if evento_atual:
                    evento_atual["pagina_final"] = pagina_num - 1
                    eventos.append(evento_atual)

                # Extração de informações do evento atual
                numero_evento = re.search(r"Evento (\d+)", texto)
                evento_atual = {
                    "numero_evento": int(numero_evento.group(1)) if numero_evento else None,
                    "pagina_inicial": pagina_num,
                    "pagina_final": None,  # Será preenchido ao encontrar o próximo evento
                }
            elif evento_atual:
                # Adiciona páginas ao evento atual
                evento_atual["pagina_final"] = pagina_num

        # Adiciona o último evento se existir
        if evento_atual:
            eventos.append(evento_atual)

        return eventos
