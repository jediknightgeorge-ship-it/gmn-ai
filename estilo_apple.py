"""Widgets con estilo "Apple" para Tkinter: botones y tarjetas con esquinas
redondeadas y bordes suavizados (antialias).

Tkinter no sabe dibujar esquinas redondeadas; aqui se dibujan con Pillow a
3x de resolucion, se reducen (antialias) y se muestran como imagen PNG con
transparencia. Todo se cachea por tamano/color, asi que cambiar de tema o
redimensionar la ventana no recalcula lo que ya se dibujo.
"""
import base64
import io
import tkinter as tk
import tkinter.font as tkfont

from PIL import Image, ImageDraw

_SUPERMUESTREO = 3
_cache_imagenes = {}


def _a_rgb(color_hex):
    c = color_hex.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def mezclar(c1, c2, t):
    """Mezcla dos colores #RRGGBB (t=0 -> c1, t=1 -> c2)."""
    a, b = _a_rgb(c1), _a_rgb(c2)
    return "#%02x%02x%02x" % tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def imagen_redondeada(ancho, alto, radio, relleno, borde=None, grosor=1):
    """PhotoImage de un rectangulo redondeado (con borde opcional)."""
    ancho, alto = max(int(ancho), 2), max(int(alto), 2)
    radio = max(0, min(int(radio), ancho // 2, alto // 2))
    clave = (ancho, alto, radio, relleno, borde, grosor)
    img = _cache_imagenes.get(clave)
    if img is not None:
        return img
    if len(_cache_imagenes) > 600:
        _cache_imagenes.clear()

    k = _SUPERMUESTREO
    base = _a_rgb(borde or relleno)
    lienzo = Image.new("RGBA", (ancho * k, alto * k), base + (0,))
    d = ImageDraw.Draw(lienzo)
    d.rounded_rectangle((0, 0, ancho * k - 1, alto * k - 1), radius=radio * k, fill=base + (255,))
    if borde:
        g = grosor * k
        d.rounded_rectangle(
            (g, g, ancho * k - 1 - g, alto * k - 1 - g),
            radius=max(0, (radio - grosor)) * k, fill=_a_rgb(relleno) + (255,),
        )
    # BOX = promedio exacto del bloque 3x3; LANCZOS "rebota" en los bordes
    # semitransparentes y deja un halo claro en las esquinas.
    lienzo = lienzo.resize((ancho, alto), Image.BOX)
    buf = io.BytesIO()
    lienzo.save(buf, "PNG")
    img = tk.PhotoImage(data=base64.b64encode(buf.getvalue()))
    _cache_imagenes[clave] = img
    return img


# ---------------------------------------------------------------------------
# TARJETAS (reemplazan a los paneles con borde cuadrado)
# ---------------------------------------------------------------------------
def crear_tarjeta(padre, radio=14):
    """Devuelve (exterior, interior, fondo). Los widgets del usuario van en
    'interior'; 'exterior' se empaqueta en la pagina; 'fondo' es el Label que
    dibuja la tarjeta redondeada detras (se repinta con pintar_tarjeta)."""
    exterior = tk.Frame(padre, bd=0, highlightthickness=0)
    fondo = tk.Label(exterior, bd=0, highlightthickness=0)
    fondo.place(x=0, y=0, relwidth=1, relheight=1)
    interior = tk.Frame(exterior, bd=0, highlightthickness=0)
    interior.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
    exterior._radio = radio
    exterior._fondo = fondo
    return exterior, interior, fondo


def pintar_tarjeta(exterior, relleno, borde, exterior_color, radio=None):
    """Repinta la tarjeta con los colores actuales (si el tamano ya es real)."""
    fondo = exterior._fondo
    exterior.configure(bg=exterior_color)
    fondo.configure(bg=exterior_color)
    w, h = exterior.winfo_width(), exterior.winfo_height()
    if w < 20 or h < 20:
        return
    r = radio if radio is not None else exterior._radio
    img = imagen_redondeada(w, h, r, relleno, borde)
    fondo.configure(image=img)
    fondo.image = img


# ---------------------------------------------------------------------------
# BOTON REDONDEADO (imita la API de tk.Button que usa el programa)
# ---------------------------------------------------------------------------
class BotonRedondo(tk.Canvas):
    _OPCIONES_PROPIAS = {"text", "command", "font", "bg", "background", "fg", "foreground",
                         "activebackground", "activeforeground", "state", "anchor", "padx", "pady",
                         "radio"}
    _enlazado_global = False

    def __init__(self, master, text="", command=None, font=("Segoe UI", 10), padx=16, pady=8,
                 radio=10, anchor="center", bg="#0071E3", fg="#FFFFFF", activebackground=None,
                 activeforeground=None, state="normal", cursor="hand2", icono="", **kw):
        kw.pop("relief", None)
        kw.pop("bd", None)
        super().__init__(master, highlightthickness=0, bd=0, cursor=cursor)
        self._icono = icono  # se dibuja aparte, en una columna fija (alinea los textos)
        self._texto = text
        self._comando = command
        self._fuente = tkfont.Font(font=font)
        self._bg = bg
        self._fg = fg
        self._abg = activebackground or bg
        self._afg = activeforeground or fg
        self._estado = state
        self._anchor = anchor
        self._padx = padx
        self._pady = pady
        self._radio = radio
        self._encima = False
        self._presionado = False
        self._img = None
        self._medir()

        self.bindtags(("BotonRedondo",) + self.bindtags())
        if not BotonRedondo._enlazado_global:
            BotonRedondo._enlazado_global = True
            self.bind_class("BotonRedondo", "<Enter>", lambda e: e.widget._al_entrar())
            self.bind_class("BotonRedondo", "<Leave>", lambda e: e.widget._al_salir())
            self.bind_class("BotonRedondo", "<ButtonPress-1>", lambda e: e.widget._al_presionar())
            self.bind_class("BotonRedondo", "<ButtonRelease-1>", lambda e: e.widget._al_soltar(e))
            self.bind_class("BotonRedondo", "<Configure>", lambda e: e.widget._redibujar())
        self.after_idle(self._redibujar)

    # ----- tamano -----
    def _medir(self):
        ancho = self._fuente.measure(self._texto) + 2 * self._padx
        alto = self._fuente.metrics("linespace") + 2 * self._pady
        super().configure(width=ancho, height=alto)

    # ----- API tipo tk.Button -----
    def configure(self, cnf=None, **kw):
        if cnf:
            kw.update(cnf)
        propias = {k: kw.pop(k) for k in list(kw) if k in self._OPCIONES_PROPIAS}
        if kw:
            super().configure(**kw)
        remedir = False
        for clave, valor in propias.items():
            if clave == "text":
                self._texto, remedir = valor, True
            elif clave == "command":
                self._comando = valor
            elif clave == "font":
                self._fuente, remedir = tkfont.Font(font=valor), True
            elif clave in ("bg", "background"):
                self._bg = valor
            elif clave in ("fg", "foreground"):
                self._fg = valor
            elif clave == "activebackground":
                self._abg = valor
            elif clave == "activeforeground":
                self._afg = valor
            elif clave == "state":
                self._estado = valor
                super().configure(cursor="arrow" if valor == tk.DISABLED else "hand2")
            elif clave == "anchor":
                self._anchor = valor
            elif clave == "padx":
                self._padx, remedir = valor, True
            elif clave == "pady":
                self._pady, remedir = valor, True
            elif clave == "radio":
                self._radio = valor
        if remedir:
            self._medir()
        if propias:
            self._redibujar()

    config = configure

    def cget(self, clave):
        if clave == "state":
            return self._estado
        if clave == "text":
            return self._texto
        if clave in ("bg", "background"):
            return self._bg
        if clave in ("fg", "foreground"):
            return self._fg
        return super().cget(clave)

    __getitem__ = cget

    def invoke(self):
        if self._estado != tk.DISABLED and self._comando:
            self._comando()

    # ----- eventos -----
    def _al_entrar(self):
        self._encima = True
        self._redibujar()

    def _al_salir(self):
        self._encima = False
        self._presionado = False
        self._redibujar()

    def _al_presionar(self):
        if self._estado != tk.DISABLED:
            self._presionado = True
            self._redibujar()

    def _al_soltar(self, e):
        activo = self._presionado
        self._presionado = False
        self._redibujar()
        if activo and 0 <= e.x <= self.winfo_width() and 0 <= e.y <= self.winfo_height():
            self.invoke()

    # ----- dibujo -----
    def _fondo_exterior(self):
        """Color de fondo del contenedor como #RRGGBB (resuelve nombres de
        color de Tk como 'SystemButtonFace' que existen antes de aplicar tema)."""
        try:
            color = self.master.cget("bg")
            if not (isinstance(color, str) and color.startswith("#") and len(color) == 7):
                r, g, b = self.winfo_rgb(color)
                color = "#%02x%02x%02x" % (r // 256, g // 256, b // 256)
            return color
        except tk.TclError:
            return "#FFFFFF"

    def _redibujar(self):
        try:
            w, h = self.winfo_width(), self.winfo_height()
            if w < 4 or h < 4:
                w, h = int(self["width"]), int(self["height"])
            exterior = self._fondo_exterior()
            super().configure(bg=exterior)
            self.delete("all")

            deshabilitado = self._estado == tk.DISABLED
            if deshabilitado:
                relleno = mezclar(self._bg, exterior, 0.6)
                texto = mezclar(self._fg, relleno, 0.5)
            elif self._presionado:
                relleno, texto = mezclar(self._abg, "#000000", 0.12), self._afg
            elif self._encima:
                relleno, texto = self._abg, self._afg
            else:
                relleno, texto = self._bg, self._fg

            img = imagen_redondeada(w, h, self._radio, relleno)
            self._img = img
            self.create_image(0, 0, anchor="nw", image=img)
            if self._anchor == "w":
                x_texto = self._padx
                if self._icono:
                    self.create_text(self._padx + 10, h / 2, text=self._icono, fill=texto,
                                     font=self._fuente, anchor="center")
                    x_texto = self._padx + 30
                self.create_text(x_texto, h / 2, text=self._texto, fill=texto, font=self._fuente, anchor="w")
            else:
                self.create_text(w / 2, h / 2, text=self._texto, fill=texto, font=self._fuente, anchor="center")
        except tk.TclError:
            pass
