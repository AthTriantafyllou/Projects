# app/pipelines/pdf_asset_extractor.py

import fitz  # PyMuPDF
import uuid
from typing import List

from pipelines.models import Asset

def group_rects(rects: List[fitz.Rect], threshold: float = 20.0) -> List[fitz.Rect]:
    """
    Ομαδοποιεί ορθογώνια που είναι κοντά μεταξύ τους.
    Αντί για distance_to, ελέγχουμε αν ένα Rect αν επεκταθεί κατά 'threshold' 
    τέμνει ένα άλλο.
    """
    if not rects:
        return []
    
    groups = []
    # Μετατρέπουμε σε λίστα για να μπορούμε να αφαιρούμε στοιχεία
    remaining = [fitz.Rect(r) for r in rects]

    while remaining:
        current_group = remaining.pop(0)
        found_neighbor = True
        
        while found_neighbor:
            found_neighbor = False
            # Χρησιμοποιούμε αντίστροφη λούπα για ασφαλή αφαίρεση
            for i in range(len(remaining) - 1, -1, -1):
                # Δημιουργούμε ένα προσωρινά μεγαλύτερο rect για τον έλεγχο γειτνίασης
                test_rect = fitz.Rect(current_group)
                test_rect.x0 -= threshold
                test_rect.y0 -= threshold
                test_rect.x1 += threshold
                test_rect.y1 += threshold
                
                # Αν το επεκταμένο rect ακουμπάει το επόμενο, τα ενώνουμε
                if test_rect.intersects(remaining[i]):
                    current_group.include_rect(remaining.pop(i))
                    found_neighbor = True
        
        groups.append(current_group)
    return groups
def extract_assets_from_pdf(pdf_path: str, user_id: int, document_id: str) -> List[Asset]:
    assets: List[Asset] = []
    doc = fitz.open(pdf_path)

    for page_index in range(len(doc)):
        page = doc[page_index]
        page_number = page_index + 1
        local_order = 0.01

        # 1. Εξαγωγή Raster Εικόνων (όπως πριν)
        images = page.get_images(full=True)
        for img in images:
            xref = img[0]
            try:
                base_image = doc.extract_image(xref)
                image_bytes = base_image.get("image")
                if image_bytes:
                    assets.append(Asset(
                        asset_id=f"img_{uuid.uuid4().hex[:8]}",
                        page=page_number,
                        asset_type="image",
                        order=local_order,
                        image_bytes=image_bytes,
                    ))
                    local_order += 0.01
            except Exception:
                continue

        # 2. Εξαγωγή Διαγραμμάτων (Vector Graphics)
        drawings = page.get_drawings()
        if len(drawings) < 3:  # Μικρό threshold για να αγνοούμε απλές γραμμές
            continue

        # Συλλέγουμε όλα τα rects των σχεδίων
        raw_rects = [fitz.Rect(d["rect"]) for d in drawings if d.get("rect")]
        
        # Ομαδοποιούμε τα σχέδια σε "νησίδες"
        diagram_groups = group_rects(raw_rects)

        # Παίρνουμε τα text blocks για να ξέρουμε πού υπάρχει κείμενο
        text_blocks = page.get_text("blocks")

        for diag_rect in diagram_groups:
            # Αν είναι πολύ λεπτό (γραμμή) ή πολύ στενό
            if diag_rect.height < 5 or diag_rect.width < 5:
                continue
            # Αν είναι μια πολύ μακριά και λεπτή γραμμή (π.χ. διαχωριστικό)
            if diag_rect.width / diag_rect.height > 20 or diag_rect.height / diag_rect.width > 20:
                continue
                
            # Αγνοούμε πολύ μικρά στοιχεία ή στοιχεία που καλύπτουν όλη τη σελίδα
            if diag_rect.width < 20 or diag_rect.height < 20:
                continue
            if diag_rect.get_area() / page.rect.get_area() > 0.95:
                text_check = page.get_text("text", clip=diag_rect).strip()
                # Αν είναι τεράστιο ΚΑΙ δεν έχει καθόλου κείμενο, μάλλον είναι πλαίσιο/φόντο
                if not text_check:
                    continue

            # --- ΒΕΛΤΙΩΣΗ: Περικοπή αν υπάρχει κείμενο ακριβώς από κάτω ---
            # Ψάχνουμε αν κάποιο block κειμένου τέμνει το κάτω μέρος του diag_rect
            for b in text_blocks:
                b_rect = fitz.Rect(b[:4])
                # Αν το κείμενο ξεκινάει μέσα στο διάγραμμα αλλά χαμηλά (π.χ. στο κάτω 15%)
                # ή αν είναι οριακά από κάτω, "μαζεύουμε" το διάγραμμα
                if diag_rect.intersects(b_rect):
                    # Αν το κείμενο είναι στο κάτω μέρος του bounding box, κόβουμε το box
                    if b_rect.y0 > diag_rect.y0 + (diag_rect.height * 0.8):
                        diag_rect.y1 = b_rect.y0 - 2

            try:
                # Χρήση υψηλότερου DPI για καθαρότητα στα διαγράμματα
                crop_rect = fitz.Rect(diag_rect)
                crop_rect.x0 -= 2
                crop_rect.y0 -= 2
                crop_rect.x1 += 2
                crop_rect.y1 += 2
                # Προσοχή να μην βγούμε έξω από τα όρια της σελίδας
                crop_rect.intersect(page.rect)
                
                pix = page.get_pixmap(clip=crop_rect, dpi=200)
                
                #pix = page.get_pixmap(clip=diag_rect, dpi=200)
                image_bytes = pix.tobytes("png")
                
                assets.append(Asset(
                    asset_id=f"diag_{uuid.uuid4().hex[:8]}",
                    page=page_number,
                    asset_type="diagram",
                    order=local_order,
                    image_bytes=image_bytes,
                ))
                local_order += 0.01
            except Exception:
                continue

    doc.close()
    return assets