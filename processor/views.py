import os
import re
import tempfile

import pymupdf
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from django.conf import settings

class ProcessorBase:
    def process(self, pdf_path):
        raise NotImplementedError("Subclasses devem implementar o método 'process'.")
    
    def extract_date(self, texto):
        raise NotImplementedError("Subclasses devem implementar o método 'extract_date'.")
    
    def pdf_text_extract(self, pdf_path):
        doc = pymupdf.open(pdf_path)
        texto_paginas = {}
        
        for pagina_num in range(len(doc)):
            pagina = doc.load_page(pagina_num)
            texto_paginas[pagina_num + 1] = pagina.get_text()
        
        return texto_paginas
    
    def rename_events(self, events):
        numero_evento = 0
        total_eventos = len(events)
        num_digitos = len(str(total_eventos))

        for event in events:
            numero_evento += 1
            event["numero_evento"] = f"{numero_evento:0{num_digitos}d}"  
       
        return events

class PJEProcessor(ProcessorBase):
    def process(self, pdf_path):
        texto_paginas = self.pdf_text_extract(pdf_path)
        eventos = self.pje_processor(texto_paginas)
        return self.rename_events(eventos)

    def extract_date(self, texto):
        """
        Extrai a data no formato DD-MM-YYYY de um texto.
        """
        match = re.search(r"\s+-\s+((?:0[1-9]|[12][0-9]|3[01])[-/](?:0[1-9]|1[0-2])[-/](?:\d{4}))", texto)
        if match:
            # Substitui / por -
            return match.group(1).replace("/", "-")
        return None

    def pje_processor(self, texto_paginas):
        eventos = []
        evento_atual = None
        total_paginas = len(texto_paginas)

        for pagina_num, texto in texto_paginas.items():
            match = re.search(r"Número do documento:\s*(\d+)", texto)
            if match:
                numero_evento = match.group(1)

                # Extrai a data da página atual
                data_evento = self.extract_date(texto)

                if evento_atual and evento_atual["numero_evento"] != numero_evento:
                    evento_atual["pagina_final"] = pagina_num - 1
                    eventos.append(evento_atual)
                    evento_atual = None

                if not evento_atual:
                    evento_atual = {
                        "numero_evento": numero_evento,
                        "pagina_inicial": pagina_num,
                        "pagina_final": None,
                        "data_evento": data_evento,
                    }

            elif evento_atual:
                evento_atual["pagina_final"] = pagina_num

                # Verifica se a data está na primeira página do evento
                if evento_atual["pagina_inicial"] == pagina_num:
                    data_na_pagina = self.extract_date(texto)

        if evento_atual:
            evento_atual["pagina_final"] = total_paginas
            eventos.append(evento_atual)

        return eventos


class EPROCProcessor(ProcessorBase):
    def process(self, pdf_path):
        texto_paginas = self.pdf_text_extract(pdf_path)
        eventos = self.eproc_processor(texto_paginas)
        return self.rename_events(eventos)
    
    def extract_date(self, texto):
        """
        Extrai a data no formato DD-MM-YYYY de um texto.
        """
        match = re.search(r"(\d{2}/\d{2}/\d{4})", texto)
        if match:
            return match.group(1).replace("/", "-")

        return None


    def eproc_processor(self, texto_paginas):
        eventos = []
        evento_atual = None

        for pagina_num, texto in texto_paginas.items():
            # Identifica a página de separação
            if "PÁGINA DE SEPARAÇÃO" in texto:
                # Fecha o evento anterior, se existir
                if evento_atual:
                    evento_atual["pagina_inicial"] += 1
                    evento_atual["pagina_final"] = pagina_num - 1

                    # Verifica se o evento é válido antes de adicioná-lo
                    if evento_atual["pagina_final"] is not None and evento_atual["pagina_inicial"] <= evento_atual["pagina_final"]:
                        eventos.append(evento_atual)

                # Extrai o número do evento
                numero_evento_match = re.search(r"Evento (\d+)", texto)
                numero_evento = int(numero_evento_match.group(1)) if numero_evento_match else None

                # Extrai a data na página de separação
                data_evento = self.extract_date(texto)

                # Inicia um novo evento
                evento_atual = {
                    "numero_evento": numero_evento,
                    "pagina_inicial": pagina_num,
                    "pagina_final": None,
                    "data_evento": data_evento,
                }
                
            else:
                # Continua atualizando a página final do evento atual
                if evento_atual:
                    evento_atual["pagina_final"] = pagina_num

                    # Verifica se a data está na primeira página do evento
                    if evento_atual["pagina_inicial"] == pagina_num:
                        data_na_pagina = self.extract_date(texto)

        # Adiciona o último evento, se ainda não foi adicionado
        if evento_atual:
            evento_atual["pagina_inicial"] += 1
            if evento_atual["pagina_final"] is not None and evento_atual["pagina_inicial"] <= evento_atual["pagina_final"]:
                eventos.append(evento_atual)

        # Verificação adicional: remove eventos sem número de evento
        eventos = [evento for evento in eventos if evento["numero_evento"] is not None]

        return eventos


class ESAJProcessor(ProcessorBase):
    def process(self, pdf_path):
        texto_paginas = self.pdf_text_extract(pdf_path)
        eventos = self.esaj_processor(texto_paginas)
        return self.rename_events(eventos)

    def extract_date(self, texto):
        """
        Extrai a data no formato DD-MM-YYYY de um texto.
        """
        match = re.search(r'(?:protocolado em|liberado nos autos em) (\d{2}/\d{2}/\d{4})', texto)
        if match:
            # Substitui / por -
            return match.group(1).replace("/", "-")
        return None

    def esaj_processor(self, texto_paginas):
        codigos = []
        eventos = []
        evento_atual = None

        for pagina_num, texto in texto_paginas.items():
            # Busca pelo código na página
            match = re.search(r'código\s([a-zA-Z0-9]{8}\.)', texto)
            if match:
                codigo = match.group(1)

                # Extrai a data do texto
                data_evento = self.extract_date(texto)

                # Se o código é novo, finalize o evento anterior
                if evento_atual and evento_atual["codigo"] != codigo:
                    eventos.append(evento_atual)
                    evento_atual = None

                # Inicia um novo evento se necessário
                if not evento_atual:
                    evento_atual = {
                        "numero_evento": len(codigos) + 1 if codigo not in codigos else codigos.index(codigo) + 1,
                        "codigo": codigo,
                        "pagina_inicial": pagina_num,
                        "pagina_final": pagina_num,  # Atualizado mais tarde
                        "data_evento": data_evento,
                    }

                # Atualiza a página final do evento atual
                evento_atual["pagina_final"] = pagina_num

                # Verifica se a data está na primeira página
                if evento_atual["pagina_inicial"] == pagina_num:
                    data_na_pagina = self.extract_date(texto)

                # Adiciona o código à lista de códigos, se ainda não existir
                if codigo not in codigos:
                    codigos.append(codigo)
            elif evento_atual:
                # Atualiza a página final enquanto o evento está ativo
                evento_atual["pagina_final"] = pagina_num

        # Finaliza o último evento, se existir
        if evento_atual:
            eventos.append(evento_atual)

        # Remove o campo 'codigo' do resultado final
        for evento in eventos:
            evento.pop("codigo", None)

        return eventos

class PROJUDIProcessor(ProcessorBase): 
    def process(self, pdf_path):
        texto_paginas = self.pdf_text_extract(pdf_path)
        eventos = self.projudi_processor(texto_paginas)
        return self.rename_events(eventos)
    
    def extract_date(self, texto):
        # OBS: PROJUDI BA não tem data de publicação do evento no PDF
        regex = (
            r"Publicado Digitalmente em (\d{2}/\d{2}/\d{4})|" # PROJUDI GO
            r"(\d{2}/\d{2}/\d{4}):" # PROJUDI AM e PR
        )

        match = re.search(regex, texto) 

        if match:
            data_evento = match.group(1) if match.group(1) else match.group(2)
            return data_evento.replace("/", "-")
        
        return None
    
    def projudi_processor(self, texto_paginas):
        codigos = []
        eventos = []
        evento_atual = None

        for pagina_num, texto in texto_paginas.items():
            # Busca pelo código na página
            # Regex para PROJUDI AM, BA, GO, PR (talvez seja necessário implementar para outros estados
            regex = (
                r"documento:\s([a-zA-Z0-9]{8}\s)|"
                r"código:\s([0-9]{27}\,)|"
                r"- Identificador:\s([A-Z0-9]{5}\s[A-Z0-9]{5}\s[A-Z0-9]{5}\s[A-Z0-9]{5})"
            )

            match = re.search(regex, texto)

            if match:
                codigo = match.group(1) or match.group(2) or match.group(3)

                data_evento = self.extract_date(texto)

                # Se o código é novo, finalize o evento anterior
                if evento_atual and evento_atual["codigo"] != codigo:
                    eventos.append(evento_atual)
                    evento_atual = None

                # Inicia um novo evento se necessário
                if not evento_atual:
                    evento_atual = {
                        "numero_evento": len(codigos) + 1 if codigo not in codigos else codigos.index(codigo) + 1,
                        "codigo": codigo,
                        "pagina_inicial": pagina_num,
                        "pagina_final": pagina_num,
                        "data_evento": data_evento,
                    }

                # Atualiza a página final do evento atual
                evento_atual["pagina_final"] = pagina_num

                # Adiciona o código à lista de códigos, se ainda não existir
                if codigo not in codigos:
                    codigos.append(codigo)
            elif evento_atual:
                # Atualiza a página final enquanto o evento está ativo
                evento_atual["pagina_final"] = pagina_num

        # Finaliza o último evento, se existir
        if evento_atual:
            eventos.append(evento_atual)

        # Remove o campo 'codigo' do resultado final
        for evento in eventos:
            evento.pop("codigo", None)

        return eventos

class TJSEProcessor(ProcessorBase):
    def process(self, pdf_path):
        texto_paginas = self.pdf_text_extract(pdf_path)
        eventos = self.tjse_processor(texto_paginas)
        return self.rename_events(eventos)

    def extract_date(self, texto):
        regex = r'DATA:\s+(\d{2}/\d{2}/\d{4})'
        match = re.search(regex, texto)
        if match:
            data_evento = match.group(1).replace("/", "-")
            return data_evento
            
    def tjse_processor(self, texto_paginas):
        codigos = []
        eventos = []
        evento_atual = None

        for pagina_num, texto in texto_paginas.items():
            # Busca pelo código na página
            # Regex para PROJUDI AM, BA, GO, PR (talvez seja necessário implementar para outros estados
            match = re.search(r'MOVIMENTO:\s+(.+)', texto)
            if match:
                codigo = match.group(1)


                # Se o código é novo, finalize o evento anterior
                if evento_atual and evento_atual["codigo"] != codigo:
                    eventos.append(evento_atual)
                    evento_atual = None

                # Inicia um novo evento se necessário
                if not evento_atual:
                    evento_atual = {
                        "numero_evento": len(codigos) + 1 if codigo not in codigos else codigos.index(codigo) + 1,
                        "codigo": codigo,
                        "pagina_inicial": pagina_num,
                        "pagina_final": pagina_num,
                        "data_evento": self.extract_date(texto),
                    }

                # Atualiza a página final do evento atual
                evento_atual["pagina_final"] = pagina_num

                # Adiciona o código à lista de códigos, se ainda não existir
                if codigo not in codigos:
                    codigos.append(codigo)
            elif evento_atual:
                # Atualiza a página final enquanto o evento está ativo
                evento_atual["pagina_final"] = pagina_num

        # Finaliza o último evento, se existir
        if evento_atual:
            eventos.append(evento_atual)

        # Remove o campo 'codigo' do resultado final
        for evento in eventos:
            evento.pop("codigo", None)

        return eventos        

class ProcessorFactory:
    def get_processor(self, sistema_processual):

        def not_implemented():
            if sistema_processual not in systems:
                raise ValueError("Sistema desconhecido.")
            
            raise NotImplementedError(f"Sistema {sistema_processual} não implementado.")

        systems = {
            "PJE": PJEProcessor,
            "E-proc": EPROCProcessor,
            "ESAJ": ESAJProcessor,
            "PROJUDI": PROJUDIProcessor,
            "TJSE": TJSEProcessor,
            
            "Creta": not_implemented,
            "Gov.br": not_implemented,
            "Siscad": not_implemented,
            "Tucujuris": not_implemented,
        }

        processor = systems.get(sistema_processual, not_implemented)
        
        return processor()

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
            # Salva o PDF temporariamente no diretório TEMP_DIR
            with tempfile.NamedTemporaryFile(suffix=".pdf", dir=settings.TEMP_DIR, delete=False) as temp_pdf:
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
            # Remove o arquivo temporário após o processamento
            if os.path.exists(temp_pdf_path):
                os.remove(temp_pdf_path)
