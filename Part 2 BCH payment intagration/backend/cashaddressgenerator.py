import bitcoin
from bip32 import BIP32, HARDENED_INDEX
from cashaddress import convert
import qrcode
import os
from PIL import Image
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import (
    CircleModuleDrawer,
    RoundedModuleDrawer,
)
from qrcode.image.styles.colormasks import SolidFillColorMask

#function to create a QRcode bitcoin cash address from know xpub and providing the child address as argument
def create_cashaddress(child): #add extra argument (child,amount) to place amount in the QRcode aswel

    #uses BIP32 to derive child pupclic keys from extenden public key
    #use acount xpup
    bip32 = BIP32.from_xpub("xpub49UJMLKJFJ83U48U409UU90I0EJOJFMKJFMKLJ8U483U38U484U89FYIHJM")
    pubkeyInBytes = bip32.get_pubkey_from_path("m/0/"+str(child))
    
    #uses bitcoin library that preforms 2 Hash algorithms after eachother to derive bitcoin address from publik Key first SHA256 then RIPEMD160 (character format is base58)
    addressLegacy = bitcoin.pubkey_to_address(pubkeyInBytes)
    
    #to avoid confusion commenpractice is to convert the legacy addres to a cashaddress
    cashaddress = convert.to_cash_address(addressLegacy)

    print (cashaddress)
    return cashaddress

def _load_icon_image(icon_path, target_size):
    # Load a raster icon (e.g., PNG) and scale to target size.
    try:
        icon = Image.open(icon_path).convert("RGBA")
        icon.thumbnail((target_size, target_size), Image.LANCZOS)
        return icon
    except Exception:
        return None

def create_QRcode(child,address,amount,icon_path=None,module_style="rounded"):    #square
    #generate QR code from cashaddres
    box_size_value = 6
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=box_size_value,
        border=1,
    )
    qr.add_data(address + "?amount=" + str(amount))
    qr.make(fit=True)

    # Optional styled modules (e.g., circles, rounded)
    module_drawers = {
        "circle": CircleModuleDrawer,
        "rounded": RoundedModuleDrawer,
    }

    if module_style in module_drawers:
        img = qr.make_image(
            image_factory=StyledPilImage,
            module_drawer=module_drawers[module_style](),
            color_mask=SolidFillColorMask(back_color=(255, 255, 255), front_color=(0, 0, 0)),
        ).convert("RGBA")
    else:
        img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")

    # Optionally overlay a centered icon (logo)
    if icon_path and os.path.exists(icon_path):
        try:
            qr_w, qr_h = img.size
            # Icon target size leaves room for a 1-module white margin
            margin_modules = 1
            margin_px = margin_modules * box_size_value
            target_size = max(8, int(min(qr_w, qr_h) * 0.2) - 2 * margin_px)
            icon = _load_icon_image(icon_path, target_size)

            # Center position with white background square behind the icon
            if icon is not None:
                icon_w, icon_h = icon.size
                # Use a 1-module padding and align background to QR module grid
                padding = margin_px
                bg_w_raw, bg_h_raw = icon_w + (2 * padding), icon_h + (2 * padding)
                # Round background size up to nearest multiple of module size
                bg_w = ((bg_w_raw + box_size_value - 1) // box_size_value) * box_size_value
                bg_h = ((bg_h_raw + box_size_value - 1) // box_size_value) * box_size_value

                # Center background, then snap its top-left to module grid
                bg_left = (qr_w - bg_w) // 2
                bg_top = (qr_h - bg_h) // 2
                bg_left = int(round(bg_left / box_size_value)) * box_size_value
                bg_top = int(round(bg_top / box_size_value)) * box_size_value
                bg_pos = (bg_left, bg_top)

                # Re-center icon within snapped background
                icon_pos = (bg_pos[0] + (bg_w - icon_w) // 2, bg_pos[1] + (bg_h - icon_h) // 2)

                # Draw solid white square as background
                bg = Image.new("RGBA", (bg_w, bg_h), (255, 255, 255, 255))
                img.alpha_composite(bg, dest=bg_pos)

                # Composite icon on top
                img.alpha_composite(icon, dest=icon_pos)
        except Exception:
            # If icon fails, proceed with plain QR
            pass

    #save QR code as PNG file
    img.convert("RGB").save(str(child) + '.png')
    
    


if __name__ == '__main__':
    number = 40
    paymentamount = 0.0089
    cashaddress = create_cashaddress(number)
    create_QRcode(number,cashaddress,paymentamount, icon_path="bitcoin-cash-circle.svg")
