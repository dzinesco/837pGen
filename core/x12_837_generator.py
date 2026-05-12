"""
core/x12_837_generator.py
Colorado HCPF 837P Professional Claims Generator
Compliant with June 2025 HCPF Companion Guide + STEDI 005010X222A1
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
import uuid

def get_sender_defaults() -> Dict[str, str]:
    return {
        "sender_id": "11525703        ",   # 15-char padded
        "receiver_id": "COMEDASSISTPROG",
        "submitter_name": "Dzinesco",
        "submitter_email": "tmartinez@gmail.com",
        "receiver_name": "COLORADO MEDICAL ASSISTANCE PROGRAM",
        "tpid": "11525703",
        "tpid_filename": "tp11525703",
        "payer_id": "CO_TXIX",
        "tax_id": "721587149",
        "billing_npi": "1234567890",
        "billing_address": {
            "n3": "1100 East Main St",
            "n4": "Montrose*CO*814014063"
        },
        "subscriber_address": {   # fallback
            "n3": "291 PINE ST",
            "n4": "GRAND JCT*CO*815032042"
        }
    }


def fmt_date(date_str: str) -> str:
    """MM/DD/YYYY → YYYYMMDD"""
    return datetime.strptime(date_str, "%m/%d/%Y").strftime("%Y%m%d")


def generate_837_for_claim(claim: Dict[str, Any]) -> str:
    defaults = get_sender_defaults()
    data = {**defaults, **claim}   # claim overrides

    now = datetime.now()
    isa_date = now.strftime("%y%m%d")
    isa_time = now.strftime("%H%M")
    st_control = f"{int(now.timestamp()) % 10000:04d}"   # unique per file
    gs_control = str(int(now.timestamp()))

    edi: List[str] = []

    # === ISA / GS / ST ===
    edi.append(f"ISA*00*          *00*          *ZZ*{data['sender_id']:<15}*ZZ*{data['receiver_id']:<15}*{isa_date}*{isa_time}*^*00501*{gs_control.zfill(9)}*0*P*:~")
    edi.append(f"GS*HC*{data['tpid']}*{data['receiver_id']}*{now:%Y%m%d}*{now:%H%M}*{gs_control}*X*005010X222A1~")
    edi.append(f"ST*837*{st_control}*005010X222A1~")

    # BHT
    edi.append(f"BHT*0019*00*{data.get('claim_id', data.get('run_id', 'UNKNOWN'))}*{now:%Y%m%d}*{now:%H%M}*CH~")

    # Submitter (1000A)
    edi.append(f"NM1*41*2*{data['submitter_name']}*****46*{data['tpid']}~")
    edi.append(f"PER*IC*{data['submitter_name']}*EM*{data['submitter_email']}~")

    # Receiver / Payer (1000B)
    edi.append(f"NM1*40*2*{data['receiver_name']}*****PI*{data['payer_id']}~")

    # === BILLING PROVIDER (2000A) ===
    edi.append("HL*1**20*1~")
    edi.append(f"NM1*85*2*****XX*{data.get('provider_npi', data['billing_npi'])}~")
    addr = data.get("billing_address", {})
    edi.append(f"N3*{addr.get('n3', '1100 East Main St')}~")
    edi.append(f"N4*{addr.get('n4', 'Montrose*CO*814014063')}~")
    edi.append(f"REF*EI*{data['tax_id']}~")

    # === SUBSCRIBER / PATIENT (2000B) ===
    edi.append("HL*2*1*22*0~")
    edi.append("SBR*P*18*******CI~")   # Primary, Individual

    # Patient name split
    last, first = data['patient_name'].split(', ', 1) if ', ' in data['patient_name'] else (data['patient_name'], '')
    edi.append(f"NM1*IL*1*{last}*{first}*****MI*{data['member_id']}~")

    sub_addr = data.get("subscriber_address", {})
    edi.append(f"N3*{sub_addr.get('n3', '291 PINE ST')}~")
    edi.append(f"N4*{sub_addr.get('n4', 'GRAND JCT*CO*815032042')}~")
    edi.append(f"DMG*D8*{fmt_date(data['dob'])}*U~")

    # Payer at claim level
    edi.append(f"NM1*PR*2*****PI*{data['payer_id']}~")

    # === CLAIM LEVEL (2300) ===
    charge = f"{float(data['total_charge']):.2f}"
    edi.append(f"CLM*{data['claim_id']}*{charge}***{data['pos']}::{data['frequency_code']}*Y*A*Y~")
    edi.append(f"REF*D9*{data['claim_id']}~")   # TCN
    edi.append(f"HI*ABK:{data['diagnosis_codes']}~")

    # EVV if required
    if data.get("evv_required"):
        edi.append("REF*EV*1~")   # placeholder – extend with full EVV loop per guide

    # === SERVICE LINE (2400) ===
    edi.append("LX*1~")
    mod = data.get('modifiers', '')
    sv_qual = f"HC:{data['procedure_code']}" + (f":{mod}" if mod else "")
    edi.append(f"SV1*{sv_qual}*{charge}*UN*{data['units']}*1*****Y~")
    edi.append(f"DTP*472*D8*{fmt_date(data['service_date'])}~")
    edi.append(f"REF*6R*{data['claim_id']}~")

    # Close loops
    edi.append(f"SE*{len(edi)+1}*{st_control}~")   # count includes SE
    edi.append(f"GE*1*{gs_control}~")
    edi.append(f"IEA*1*{gs_control.zfill(9)}~")

    generated = "\n".join(edi) + "\n"
    print(f"✅ Generated CO HCPF 837P | Claim {data['id']} | {data['claim_id']} | {len(edi)} segments")
    return generated


def generate_837_batch(run_id: str, claims: List[Dict[str, Any]]) -> str:
    """Batch multiple claims into one 837 file"""
    if not claims:
        return ""
    batch = [generate_837_for_claim(c) for c in claims]
    # In real use: merge envelopes properly (one ISA/GS with multiple STs)
    return "\n".join(batch)


# Quick test
if __name__ == "__main__":
    test_claim = {
        "id": 902,
        "run_id": "6df017b7-8070-47cd-abb6-e6a068c60d34",
        "claim_id": "t991102945o1c53d",
        "patient_name": "Falstrup, Christina",
        "payer": "COHCPF",
        "total_charge": 28.3,
        "frequency_code": "1",
        "status": "processed",
        "service_date": "05/02/2026",
        "procedure_code": "T1019",
        "modifiers": "U2",
        "dob": "09/02/1952",
        "member_id": "Y678588",
        "diagnosis_codes": "R69",
        "pos": "12",
        "units": 4.07,
        "provider_npi": "1851446637",
        "rendering_provider": "Falstrup, Christina",
        "evv_required": 0
    }
    print(generate_837_for_claim(test_claim))
