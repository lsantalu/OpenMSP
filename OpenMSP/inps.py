from django.shortcuts import render
from django.http import HttpResponse

from impostazioni.models import UtentiParametri
from impostazioni.models import InpsIseeParametri
from impostazioni.models import InpsDurcParametri
from impostazioni.models import DatiEnte

from .utils import salva_log
from .utils import converti_data
from .verifica_cf import verifica_cf
from .verifica_cf import verifica_cf_azienda

import xmltodict
import urllib.parse
import base64
import datetime
import uuid
import jwt
import subprocess
import requests
import json
import io
import csv
import sys
import openpyxl
from decimal import Decimal, InvalidOperation


TIPO_PRESTAZIONE_DA_EROGARE = [
    ("A1.01", "Assegno per il nucleo familiare erogati dai comuni"),
    ("A1.02", "Assegno Maternità erogato dai Comuni"),
    ("A1.03", "Carta acquisti"),
    ("A1.04", "Contributi economici a integrazione del reddito Familiare"),
    ("A1.05", "Contributi economici per alloggio"),
    ("A1.06", "Buoni spesa o buoni pasto"),
    ("A1.07", "Contributi e integrazioni a rette per asili nido"),
    ("A1.08", "Contributi e integrazioni a rette per servizi integrativi o innovativi per la prima infanzia"),
    ("A1.09", "Contributi economici per i servizi scolastici"),
    ("A1.10", "Contributi economici per cure o prestazioni sociali a rilevanza sanitaria"),
    ("A1.11", "Assegnazioni economiche per il sostegno della domiciliarità e dell'autonomia personale"),
    ("A1.12", "Contributi e integrazioni a rette per accesso a centri Diurni"),
    ("A1.13", "Contributi e integrazioni a rette per accesso ai servizi semi-residenziali"),
    ("A1.14", "Contributi e integrazioni a rette per accesso a servizi Residenziali"),
    ("A1.15", "Contributi per servizi alla persona"),
    ("A1.16", "Contributi economici per servizio trasporto e mobilità"),
    ("A1.17", "Contributi economici erogati a titolo di prestito/prestiti d'onore"),
    ("A1.18", "Contributi economici per l'inserimento lavorativo"),
    ("A1.19", "Borse di studio"),
    ("A1.20", "Buono vacanze"),
    ("A2.01", "Mensa sociale"),
    ("A2.02", "Sostegno socio-educativo territoriale o domiciliare"),
    ("A2.03", "Prestazioni del diritto allo studio universitario"),
    ("A2.04", "Agevolazioni per tasse universitarie"),
    ("A2.05", "Agevolazioni per i servizi di pubblica utilità (telefono, luce, gas)"),
    ("A2.06", "Agevolazioni tributarie comunali (nettezza urbana, ecc.)"),
    ("A2.07", "Assistenza domiciliare socio-assistenziale"),
    ("A2.08", "A.D.I.- Assistenza domiciliare integrata con servizi Sanitari"),
    ("A2.09", "Supporto all'inserimento lavorativo"),
    ("A2.10", "Servizi integrativi per la prima infanzia"),
    ("A2.11", "Sostegno socio-educativo scolastico"),
    ("A2.12", "Mensa scolastica"),
    ("A3.01", "Strutture semiresidenziali"),
    ("A3.02", "Strutture residenziali"),
    ("A3.03", "Asilo Nido"),
    ("Z9.99", "Altro"),
]

TIPO_PRESTAZIONE_DA_EROGARE_MAP = dict(TIPO_PRESTAZIONE_DA_EROGARE)

def _get_node_by_suffix(data, suffix):
    if not isinstance(data, dict):
        return {}

    for key, value in data.items():
        if key == suffix or key.endswith(f":{suffix}"):
            return value
    return {}


def _ensure_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _humanize_key(key):
    key = key.lstrip('@').replace('_', ' ')
    output = []
    for index, char in enumerate(key):
        if index > 0 and char.isupper() and key[index - 1].islower():
            output.append(' ')
        output.append(char)
    return ''.join(output).strip()


def _format_euro(value):
    if value in (None, ""):
        return value

    try:
        amount = Decimal(str(value).replace(",", "."))
    except (InvalidOperation, ValueError):
        return value

    formatted = f"{amount:,.2f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"€ {formatted}"


def _format_date(value):
    if value in (None, ""):
        return value

    text = str(value).strip()
    for date_format in ("%Y-%m-%d", "%d-%m-%Y"):
        try:
            parsed = datetime.datetime.strptime(text, date_format)
            return parsed.strftime("%d/%m/%Y")
        except ValueError:
            continue
    return value


def _is_euro_field(label):
    normalized = label.lower().replace(" ", "")
    euro_tokens = (
        "isee",
        "ise",
        "isr",
        "isp",
        "reddito",
        "patrimonio",
        "detrazione",
        "somma",
        "valore",
        "saldo",
        "consistenzamedia",
    )
    return any(token in normalized for token in euro_tokens)


def _is_date_field(label):
    normalized = label.lower().replace(" ", "")
    date_tokens = (
        "data",
        "rilascio",
        "presentazione",
        "scadenza",
        "validita",
        "inizio",
        "fine",
        "controllo",
    )
    return any(token in normalized for token in date_tokens)


def _format_section_currency_fields(sections):
    for section in sections:
        for field in section.get("fields", []):
            if _is_euro_field(field.get("label", "")):
                field["value"] = _format_euro(field.get("value"))
            elif _is_date_field(field.get("label", "")):
                field["value"] = _format_date(field.get("value"))


def _collect_display_sections(node, title, sections):
    if isinstance(node, dict):
        fields = []
        child_nodes = []

        for key, value in node.items():
            if key.startswith('@'):
                fields.append({"label": _humanize_key(key), "value": value})
            elif isinstance(value, (dict, list)):
                child_nodes.append((key, value))
            else:
                fields.append({"label": _humanize_key(key), "value": value})

        if fields:
            sections.append({"title": title, "fields": fields})

        for key, value in child_nodes:
            child_title = _humanize_key(key)
            if isinstance(value, list):
                for index, item in enumerate(value, start=1):
                    _collect_display_sections(item, f"{child_title} {index}", sections)
            else:
                _collect_display_sections(value, child_title, sections)

    elif isinstance(node, list):
        for index, item in enumerate(node, start=1):
            _collect_display_sections(item, f"{title} {index}", sections)
    elif node not in (None, ""):
        sections.append({"title": title, "fields": [{"label": title, "value": node}]})


def _extract_first_indicator(ordinario):
    indicator_map = [
        ("ISEEOrdinario", "Ordinario"),
        ("ISEEFamiglia", "Famiglia"),
    ]

    for key, label in indicator_map:
        section = ordinario.get(key, {})
        if isinstance(section, dict) and section.get('Valori'):
            return label, section

    return None, {}

def _get_inps_token(parametri):
    issued = datetime.datetime.utcnow()
    delta = datetime.timedelta(minutes=43200)
    expire_in = issued + delta
    jti = uuid.uuid4()

    headers_rsa = {
        "kid": parametri.kid,
        "alg": parametri.alg,
        "typ": parametri.typ
    }

    payload = {
        "iss": parametri.iss,
        "sub": parametri.sub,
        "aud": parametri.aud,
        "purposeId": parametri.purposeid,
        "jti": str(jti),
        "iat": issued,
        "exp": expire_in
    }

    asserzione = jwt.encode(payload, parametri.private_key, algorithm="RS256", headers=headers_rsa)

    curl_command = (
        f"curl --location --silent --request POST {parametri.baseurlauth}/token.oauth2 "
        f"--header 'Content-Type: application/x-www-form-urlencoded' "
        f"--data-urlencode 'client_id={parametri.iss}' "
        f"--data-urlencode 'client_assertion={asserzione}' "
        "--data-urlencode 'client_assertion_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer' "
        "--data-urlencode 'grant_type=client_credentials'"
    )

    if not sys.platform.startswith('linux'):
        curl_command = curl_command.replace("'", '"')

    result = subprocess.run(curl_command, shell=True, capture_output=True, text=True)
    try:
        data = json.loads(result.stdout)
        voucher = data.get('access_token', '')
    except json.JSONDecodeError:
        voucher = ""

    # Estrae il token_id (jti) dal voucher
    try:
        decoded_token = jwt.decode(voucher, options={"verify_signature": False})
        token_id = decoded_token.get('jti')
    except:
        token_id = None

    return voucher, token_id


def inps_isee(request):
    if request.user.id:
        utente_sessione = UtentiParametri.objects.get(id=request.user.id)
        utente_abilitato = utente_sessione.inps_isee
        selected_prestazione = ''
        if request.method == 'POST':
            data = []
            cf = request.POST.get('input_CF', '').strip()
            selected_prestazione = request.POST.get('tipo_prestazione_da_erogare', '').strip()
            data.append(cf)
            correttezza_cf = verifica_cf(cf) if cf else 0
            if not selected_prestazione:
                data.append("Prestazione da erogare non selezionata")
                salva_log(request.user, "Verifica INPS - ISEE", "Tentativo verifica senza prestazione per utente " + cf)
            elif correttezza_cf == 1 or correttezza_cf == 2:
                bearer, tok_id = inps_isee_get_bearer()
                res_data, status, purp_id = RichiestaIsee(cf, bearer, selected_prestazione)
                data.append(res_data)
                data = converti_data(data)
                salva_log(request.user, "Verifica INPS - ISEE", "Verificato utente " + cf, purposeid=purp_id, resp_status=status, token_id=tok_id)
            else:
                data.append("Codice fiscale non corretto")
                salva_log(request.user, "Verifica INPS - ISEE", "Verificato utente " + cf)

            return render(request, 'inps_isee.html', {
                'data': data,
                'utente_abilitato': utente_abilitato,
                'tipo_prestazione_da_erogare': TIPO_PRESTAZIONE_DA_EROGARE,
                'selected_prestazione': selected_prestazione,
            })
    else:
        utente_abilitato = False
    return render(request, 'inps_isee.html', {
        'utente_abilitato': utente_abilitato,
        'tipo_prestazione_da_erogare': TIPO_PRESTAZIONE_DA_EROGARE if request.user.id else [],
        'selected_prestazione': selected_prestazione if request.user.id else '',
    })


def inps_isee_get_bearer():
    parametri_inps_isee = InpsIseeParametri.objects.get(id=1)
    return _get_inps_token(parametri_inps_isee)


def RichiestaIsee(cf, bearer, prestazione_da_erogare="A1.01"):
    parametri_inps_isee = InpsIseeParametri.objects.get(id=1)
    url = parametri_inps_isee.target
    dati_ente = DatiEnte.objects.first()
    data_validita = datetime.date.today().isoformat()

    # SOAP Action dalla specifica WSDL
    soap_action = "http://inps.it/ConsultazioneISEE/ISvcConsultazione/ConsultazioneAttestazioneResidenti"

    headers = {
        "Authorization": f"Bearer {bearer}",
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": f'"{soap_action}"',
        "INPS-Identity-UserId": dati_ente.cf,
        "INPS-Identity-CodiceUfficio": "001"
    }

    # Costruzione dell'inviluppo SOAP basato sull'XSD e sull'XML di esempio fornito
    body = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:con="http://inps.it/ConsultazioneISEE">
   <soapenv:Header>
      <inps:Identity xmlns:inps="http://inps.it/">
         <UserId>{dati_ente.cf}</UserId>
         <CodiceUfficio>001</CodiceUfficio>
      </inps:Identity>
   </soapenv:Header>
   <soapenv:Body>
      <con:ConsultazioneAttestazioneResidenti>
         <con:request>
            <con:RicercaCF>
               <con:CodiceFiscale>{cf}</con:CodiceFiscale>
               <con:DataValidita>{data_validita}</con:DataValidita>
               <con:PrestazioneDaErogare>{prestazione_da_erogare}</con:PrestazioneDaErogare>
               <con:ProtocolloDomandaEnteErogatore>OpenMSP-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}</con:ProtocolloDomandaEnteErogatore>
               <con:StatodomandaPrestazione>Da Erogare</con:StatodomandaPrestazione>
            </con:RicercaCF>
         </con:request>
      </con:ConsultazioneAttestazioneResidenti>
   </soapenv:Body>
</soapenv:Envelope>"""

    try:
        response = requests.post(url, headers=headers, data=body.encode('utf-8'))
        status_code = response.status_code
        purposeid = parametri_inps_isee.purposeid

        if response.status_code == 200:
            try:
                # Parsing della risposta XML
                dict_data = xmltodict.parse(response.content)
                # Estrazione del risultato dal body SOAP
                envelope = _get_node_by_suffix(dict_data, 'Envelope')
                body = _get_node_by_suffix(envelope, 'Body')
                response_node = _get_node_by_suffix(body, 'ConsultazioneAttestazioneResidentiResponse')
                result = _get_node_by_suffix(response_node, 'ConsultazioneAttestazioneResidentiResult')

                if not result:
                    return {
                        "error": "Risposta SOAP priva del nodo ConsultazioneAttestazioneResidentiResult",
                        "raw_response": response.text[:1000],
                        "PrestazioneDaErogareCodice": prestazione_da_erogare,
                        "PrestazioneDaErogareMotivo": TIPO_PRESTAZIONE_DA_EROGARE_MAP.get(prestazione_da_erogare, ""),
                    }, status_code, purposeid

                result['DataValiditaRichiesta'] = _format_date(data_validita)
                result['PrestazioneDaErogareCodice'] = prestazione_da_erogare
                result['PrestazioneDaErogareMotivo'] = TIPO_PRESTAZIONE_DA_EROGARE_MAP.get(prestazione_da_erogare, '')

                # Decodifica dell'XML base64 se presente (contiene i dati reali dell'attestazione)
                xml_base64 = result.get('XmlEsitoAttestazione')
                if xml_base64:
                    try:
                        decoded_xml = base64.b64decode(xml_base64).decode('utf-8')
                        attestazione_dict = xmltodict.parse(decoded_xml)

                        esito_attestazione = attestazione_dict.get('EsitoAttestazione', {})
                        att = attestazione_dict.get('Attestazione', {}) or esito_attestazione.get('Attestazione', {})
                        ricerca = esito_attestazione.get('Ricerca', {})

                        result['AttestazioneXml'] = decoded_xml
                        result['AttestazioneRaw'] = att
                        result['RicercaRaw'] = ricerca

                        # Mappatura campi generali dell'attestazione
                        result['CodiceFiscaleDichiarante'] = att.get('@CodiceFiscaleDichiarante')
                        result['NumeroProtocolloDSU'] = att.get('@NumeroProtocolloDSU')
                        result['ProtocolloMittente'] = att.get('@ProtocolloMittente')
                        result['DataSottoscrizione'] = _format_date(att.get('@DataPresentazione'))
                        result['DataPresentazione'] = _format_date(att.get('@DataPresentazione'))
                        result['DataValiditaAttestazione'] = _format_date(att.get('@DataValidita'))
                        result['DataScadenza'] = _format_date(att.get('@DataScadenzaDSUCorrente'))

                        ordinario = att.get('Ordinario', {})
                        tipo_isee, indicator_section = _extract_first_indicator(ordinario)
                        indicator_values = indicator_section.get('Valori', {}) if isinstance(indicator_section, dict) else {}
                        modalita_key = next(
                            (key for key in indicator_section.keys() if key.startswith('ModalitaCalcolo')),
                            None
                        ) if isinstance(indicator_section, dict) else None
                        modalita_values = indicator_section.get(modalita_key, {}) if modalita_key else {}

                        result['TipoISEE'] = tipo_isee
                        result['ValoreISEE'] = _format_euro(indicator_values.get('@ISEE'))
                        result['ValoreISE'] = _format_euro(indicator_values.get('@ISE'))
                        result['ValoreISR'] = _format_euro(indicator_values.get('@ISR'))
                        result['ValoreISP'] = _format_euro(indicator_values.get('@ISP'))
                        result['ScalaEquivalenza'] = indicator_values.get('@ScalaEquivalenza')
                        result['DataRilascioIndicatore'] = _format_date(indicator_section.get('@DataRilascio')) if isinstance(indicator_section, dict) else None
                        result['ModalitaCalcolo'] = [
                            {
                                "label": _humanize_key(key),
                                "value": _format_euro(value) if _is_euro_field(_humanize_key(key)) else value,
                            }
                            for key, value in modalita_values.items()
                            if key.startswith('@')
                        ]

                        componenti_nucleo = []
                        for componente in _ensure_list(ordinario.get('NucleoFamiliare', {}).get('ComponenteNucleo')):
                            if isinstance(componente, dict):
                                componenti_nucleo.append({
                                    "RapportoConDichiarante": componente.get('@RapportoConDichiarante'),
                                    "Cognome": componente.get('@Cognome'),
                                    "Nome": componente.get('@Nome'),
                                    "CodiceFiscale": componente.get('@CodiceFiscale'),
                                })
                        result['ComponentiNucleo'] = componenti_nucleo

                        attestazione_sezioni = []
                        ricerca_sezioni = []
                        _collect_display_sections(att, "Attestazione", attestazione_sezioni)
                        _collect_display_sections(ricerca, "Ricerca", ricerca_sezioni)
                        _format_section_currency_fields(attestazione_sezioni)
                        _format_section_currency_fields(ricerca_sezioni)
                        result['AttestazioneSezioni'] = attestazione_sezioni
                        result['RicercaSezioni'] = ricerca_sezioni
                        result['AttestazioneJson'] = json.dumps(att, indent=2, ensure_ascii=False)
                        result['RicercaJson'] = json.dumps(ricerca, indent=2, ensure_ascii=False) if ricerca else ""

                    except Exception as e:
                        result['error_parsing_attestazione'] = str(e)
                else:
                    result['warning'] = "XmlEsitoAttestazione assente nella risposta"

                return result, status_code, purposeid
            except Exception as e:
                return {
                    "error": f"Errore nel parsing XML: {str(e)}",
                    "PrestazioneDaErogareCodice": prestazione_da_erogare,
                    "PrestazioneDaErogareMotivo": TIPO_PRESTAZIONE_DA_EROGARE_MAP.get(prestazione_da_erogare, ''),
                }, status_code, purposeid
        else:
            return False, status_code, purposeid
    except Exception as e:
        return {
            "error": f"Errore nella richiesta: {str(e)}",
            "PrestazioneDaErogareCodice": prestazione_da_erogare,
            "PrestazioneDaErogareMotivo": TIPO_PRESTAZIONE_DA_EROGARE_MAP.get(prestazione_da_erogare, ''),
        }, 500, parametri_inps_isee.purposeid


def inps_durc_get_bearer():
    parametri_inps_durc = InpsDurcParametri.objects.get(id=1)
    return _get_inps_token(parametri_inps_durc)


def inps_durc_singolo(request):
    if request.user.id:
        utente_sessione = UtentiParametri.objects.get(id=request.user.id)
        utente_abilitato = utente_sessione.inps_durc_singolo
        if request.method == 'POST':
            data = []
            cf = request.POST.get('input_CF')
            data.append(cf)

            if len(cf) == 11:
                correttezza_cf = verifica_cf_azienda(cf)
            else:
                correttezza_cf = verifica_cf(cf)

            if correttezza_cf == 1 or correttezza_cf == 2:
                bearer, tok_id = inps_durc_get_bearer()
                res_data, status, purp_id = inps_durc_verifica_impresa(cf, bearer)
                if res_data and 'del' in res_data:
                    try:
                        date_str = res_data['del'].split('T')[0]
                        date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d')
                        scadenza = date_obj + datetime.timedelta(days=120)
                        res_data['scadenza'] = scadenza.strftime('%Y-%m-%d')
                    except Exception as e:
                        pass
                data.append(res_data)
                data = converti_data(data)
                salva_log(request.user, "Verifica INPS - DURC", "Verificato utente " + cf, purposeid=purp_id, resp_status=status, token_id=tok_id)
            else:
                data.append("Codice fiscale non corretto")
                salva_log(request.user, "Verifica INPS - DURC", "Verificato utente " + cf)

            return render(request, 'inps_durc_singolo.html', {'data': data, 'utente_abilitato': utente_abilitato })
    else:
        utente_abilitato = False
    return render(request, 'inps_durc_singolo.html', { 'utente_abilitato': utente_abilitato })


def inps_durc_massivo(request):
    if request.user.id:
        utente_sessione = UtentiParametri.objects.get(id=request.user.id)
        utente_abilitato = utente_sessione.inps_durc_massivo
        if request.method == 'POST' and 'cf_csv' in request.FILES:
            csv_file = request.FILES['cf_csv']
            data = []
            cfs = []

            # Lettura CF dal file
            if csv_file.name.lower().endswith('.csv'):
                try:
                    csv_file_text = io.TextIOWrapper(csv_file.file, encoding='utf-8')
                    csv_reader = csv.reader(csv_file_text)
                    for row in csv_reader:
                        if row and row[0]:
                            cfs.append(row[0].strip().upper())
                except Exception as e:
                    return render(request, 'inps_durc_massivo.html', {'error': f"Errore lettura CSV: {str(e)}", 'utente_abilitato': utente_abilitato})
            elif csv_file.name.lower().endswith('.xlsx'):
                try:
                    wb = openpyxl.load_workbook(csv_file)
                    sheet = wb.active
                    for row in sheet.iter_rows(min_row=1, values_only=True):
                        if row and row[0]:
                            cfs.append(str(row[0]).strip().upper())
                except Exception as e:
                    return render(request, 'inps_durc_massivo.html', {'error': f"Errore lettura Excel: {str(e)}", 'utente_abilitato': utente_abilitato})

            if cfs:
                bearer, tok_id = inps_durc_get_bearer()
                for cf in cfs:
                    if len(cf) == 11:
                        correttezza_cf = verifica_cf_azienda(cf)
                    else:
                        correttezza_cf = verifica_cf(cf)

                    item = {'cf': cf, 'correttezza_cf': correttezza_cf}

                    if correttezza_cf == 1 or correttezza_cf == 2:
                        res_data, status, purp_id = inps_durc_verifica_impresa(cf, bearer)
                        if res_data:
                            # Calcolo scadenza come in singolo
                            if 'del' in res_data:
                                try:
                                    date_str = res_data['del'].split('T')[0]
                                    date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d')
                                    scadenza = date_obj + datetime.timedelta(days=120)
                                    res_data['scadenza'] = scadenza.strftime('%Y-%m-%d')
                                except:
                                    pass
                            item['res_data'] = res_data
                            salva_log(request.user, "Verifica INPS - DURC massivo", "Verificato utente " + cf, purposeid=purp_id, resp_status=status, token_id=tok_id)
                        else:
                            item['error'] = "Dati non disponibili o errore API"
                    else:
                        item['error'] = "Codice fiscale non corretto"

                    data.append(item)

            return render(request, 'inps_durc_massivo.html', {'data': data, 'utente_abilitato': utente_abilitato })
    else:
        utente_abilitato = False
    return render(request, 'inps_durc_massivo.html', { 'utente_abilitato': utente_abilitato })


def inps_durc_verifica_impresa(cf, bearer):
    inps_durc_parametri = InpsDurcParametri.objects.get(id=1)
    url = inps_durc_parametri.target + '/getDurcInCorsoDiValidita'
    dati_ente = DatiEnte.objects.first()


    headers = {
        "Authorization": f"Bearer {bearer}",
        "Content-Type": "application/json" ,
        "INPS-Identity-UserId": dati_ente.cf ,
        "INPS-Identity-CodiceUfficio": "001"
        }
    data = {
        "codicefiscale": cf
        }

    response = requests.post(url, headers=headers, json=data)
    status_code = response.status_code
    purposeid = inps_durc_parametri.purposeid

    if response.status_code == 200:
        json_data = response.json()
        return json_data, status_code, purposeid
    else:
        return False, status_code, purposeid


def _salva_impostazioni_inps(request, modello, nome_servizio):
    if request.method == 'POST':
        campi = ['kid', 'alg', 'typ', 'iss', 'sub', 'aud', 'purposeid', 'audience', 'baseurlauth', 'target', 'clientid', 'private_key', 'ver_eservice']
        dati_post = {campo: request.POST.get(campo) for campo in campi}
        dati = modello(id=1, **dati_post)
        dati.save()
        salva_log(request.user, f"Impostazioni INPS - {nome_servizio}", "modifica parametri")


def impostazioni_inps_durc(request):
    _salva_impostazioni_inps(request, InpsDurcParametri, "DURC")
    parametri_inps_durc = InpsDurcParametri.objects.all()
    return render(request, 'impostazioni_inps_durc.html', {'parametri_inps_durc': parametri_inps_durc})


def impostazioni_inps_isee(request):
    _salva_impostazioni_inps(request, InpsIseeParametri, "ISEE")
    parametri_inps_isee = InpsIseeParametri.objects.all()
    return render(request, 'impostazioni_inps_isee.html', {'parametri_inps_isee': parametri_inps_isee})


def inps_durc_download(request, protocollo):
    if request.user.id:
        utente_sessione = UtentiParametri.objects.get(id=request.user.id)
        if utente_sessione.inps_durc_singolo or utente_sessione.inps_durc_massivo:
            bearer, tok_id = inps_durc_get_bearer()
            inps_durc_parametri = InpsDurcParametri.objects.get(id=1)
            dati_ente = DatiEnte.objects.first()

            # Costruzione URL per il download secondo specifica YAML
            safe_protocollo = urllib.parse.quote(protocollo)
            url = f"{inps_durc_parametri.target}/downloadDURC/{safe_protocollo}/ITA"

            headers = {
                "Authorization": f"Bearer {bearer}",
                "INPS-Identity-UserId": dati_ente.cf,
                "INPS-Identity-CodiceUfficio": "001"
            }

            try:
                response = requests.get(url, headers=headers)

                if response.status_code == 200:
                    res_json = response.json()
                    base64_data = res_json.get('base64')

                    if base64_data:
                        # Decodifica dei dati base64 in binario
                        pdf_content = base64.b64decode(base64_data)

                        file_name = f"DURC_{protocollo}.pdf"
                        django_response = HttpResponse(pdf_content, content_type='application/pdf')
                        django_response['Content-Disposition'] = f'attachment; filename="{file_name}"'

                        salva_log(request.user, "Download DURC", f"Scaricato PDF per protocollo {protocollo}", purposeid=inps_durc_parametri.purposeid, resp_status=response.status_code, token_id=tok_id)
                        return django_response
                    else:
                        return HttpResponse("Dati PDF non trovati nella risposta", status=500)
                else:
                    return HttpResponse(f"Errore API INPS: {response.status_code}", status=response.status_code)
            except Exception as e:
                return HttpResponse(f"Eccezione durante il download: {str(e)}", status=500)

    return HttpResponse("Non autorizzato", status=403)
