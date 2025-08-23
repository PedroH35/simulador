import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from fpdf import FPDF
from io import BytesIO
import tempfile
import os

# -----------------------------
# Densidades e energia relativa dos explosivos (g/cm³, %)
# -----------------------------
explosivos = {
    "ANFO": {"densidade": 0.90},
    "Dinamite granulada": {"densidade": 1.1},
    "Dinamite gelatina": {"densidade": 1.4},
    "Lama encartuchada": {"densidade": 1.2}
}

# Parâmetros geotécnicos do maciço rochoso (exemplo genérico)
macicos = {
    "Rocha friável de baixa dureza": {"A": 3},
    "Rocha branda e pouco fraturada": {"A": 5},
    "Rocha dura e altamente fraturada": {"A": 10},
    "Rocha altamente dura e pouco fraturada": {"A": 12}    
}

malha = {
    "Aberta": {"B": 6.5},
    "Fechada": {"B": 3}
}

# -----------------------------
# Funções de cálculo
# -----------------------------
def calcular_espacamento(H, B):
    return 0.23 * (H + 2 * B)

def calcular_qe(densidade, diametro, altura_total):
    diametro_cm = diametro / 10  # mm → cm
    area_cm2 = (np.pi / 4) * diametro_cm**2  # cm²
    massa_linear_g_cm = area_cm2 * densidade  # g/cm
    comprimento_cm = altura_total * 100  # m → cm
    massa_total_g = massa_linear_g_cm * comprimento_cm  # g
    return massa_total_g / 1000  # kg

def calcular_x50(A, K, Qe):
    return A * (K**-0.8) * (Qe**(1/6))
# -----------------------------
# Interface Streamlit
# -----------------------------
st.set_page_config(page_title="Simulador de Detonação", layout="wide")
st.title("MODELAGEM DA INFLUÊNCIA DO PLANO DE FOGO NA FRAGMENTAÇÃO EM DESMONTE DE ROCHAS")

col1, col2 = st.columns(2)
with col1:
    explosivo_tipo = st.selectbox("Tipo de Explosivo", list(explosivos.keys()))
    macico_tipo = st.selectbox("Tipo de Maciço Rochoso", list(macicos.keys()))
    malha_tipo = st.selectbox("Tipo de Malha", list(malha.keys()))
    A = macicos[macico_tipo]["A"]
    afastamento = malha[malha_tipo]["B"]
    altura = st.slider("Altura do Banco (m)", 2.0, 15.0, 10.0)
    subperf = 0.6 #valor fixo em m (8*diâmetro)
    inclinacao = 15  # valor fixo em graus (remoção do controle deslizante)", 0.0, 30.0, 15.0)
    inclinacao_rad = np.radians(inclinacao)
    altura_total = (altura + subperf) / np.cos(inclinacao_rad)  # ajuste do comprimento do furo
    furos_linha = st.slider("Nº de Furos por Linha", 1, 8, 5)
    linhas = st.slider("Nº de Linhas de Furo", 1, 5, 4)

diametro = 76.2  # mm
S = calcular_espacamento(altura, afastamento)
densidade = explosivos[explosivo_tipo]["densidade"]
Qe = calcular_qe(densidade, diametro, altura_total)
n_furos = furos_linha * linhas
massa_total = Qe * n_furos

# Volume fragmentado por furo
V = S * afastamento * altura
K = Qe / V  # razão de carga (kg/m³)
X50 = calcular_x50(A, K, Qe)  # cm
X50_mm = X50 * 10

with col2:
    st.subheader("Resultados do Plano de Fogo")
    st.info(f"Comprimento real do furo: {altura_total:.2f} m")
    st.info(f"Carga por furo estimada: {Qe:.2f} kg")
    st.info(f"Espaçamento calculado: {S:.2f} m")
    st.info(f"Quantidade total de furos: {n_furos}")
    st.info(f"Massa total de explosivo: {massa_total:.1f} kg")
    st.info(f"Razão de carga (K): {K:.2f} kg/m³")
    st.success(f"Tamanho médio estimado dos fragmentos (X50): {X50_mm:.1f} mm")

    st.subheader("Plano de Fogo")
    fig, ax = plt.subplots()
    for i in range(linhas):
        for j in range(furos_linha):
            x = j * S
            y = i * afastamento
            ax.plot(x, y, 'ro')
    ax.set_aspect('equal')
    ax.set_title("Plano de Fogo (malha)")
    ax.set_xlabel("Espaçamento entre furos (m)")
    ax.set_ylabel("Afastamento entre linhas (m)")
    st.pyplot(fig)

    # Cálculo de n (índice de uniformidade)
    D = diametro  # mm
    W = 0.1  # desvio médio do furo [m], valor arbitrário
    L = altura_total  # comprimento da carga ≈ altura do furo
    n = (2.2 - 14 * (afastamento / D)) * ((1 + (S / afastamento) / 2)**0.5) * ((1 - (W / afastamento)) * (L / altura)) 
    #n = max(n, 0.5)  # garantir valor positivo

    # Gráfico de Rosin-Rammler (ajustado com X em mm e escala log)
    st.subheader("Distribuição Granulométrica para Diferentes Maciços")
    x_mm = np.logspace(0, 4, 100)  # de 1 mm a 1000 mm
    fig2, ax = plt.subplots()

    for nome, props in malha.items():
        B = props["B"]
        S_temp = calcular_espacamento(altura, B)  # recalcula espaçamento p/ cada malha
        V_temp = S_temp * B * altura
        K_temp = Qe / V_temp
        X50_temp = calcular_x50(A, K, Qe) * 10  # em mm
        R = np.exp(-0.693 * (x_mm / X50_temp)**n)
        P = 100 * (1 - R)
        ax.plot(x_mm, P, label=f"Malha {nome}")

    ax.set_xscale("log")
    ax.set_xlabel("Abertura da peneira (mm)")
    ax.set_ylabel("% Passante")
    ax.set_title("Curvas Rosin-Rammler")
    ax.legend(bbox_to_anchor=(1.05, 1), loc='lower left')
    ax.grid(True, which="both", linestyle='--', linewidth=0.5)
    st.pyplot(fig2)

def gerar_pdf(fig_fogo, fig_granulo):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Relatório Técnico - Plano de Fogo", ln=True, align="C")
    pdf.ln(10)

    # Página 1 - Plano de Fogo
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_fogo:
        fig_fogo.savefig(tmp_fogo.name, format='png')
        pdf.image(tmp_fogo.name, x=10, w=180)

    # Página 2 - Curva Granulométrica
    pdf.add_page()
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt="Distribuição Granulométrica (Rosin-Rammler):", ln=True)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_granulo:
        fig_granulo.savefig(tmp_granulo.name, format='png')
        pdf.image(tmp_granulo.name, x=10, w=180)

    # Exportar para memória
    buffer = BytesIO()
    pdf_output = pdf.output(dest='S').encode('latin1')  # Gera como string
    buffer = BytesIO(pdf_output)
    buffer.seek(0)

    # Apagar arquivos temporários
    os.remove(tmp_fogo.name)
    os.remove(tmp_granulo.name)

    return buffer

# Botão para exportar PDF
st.subheader("📄 Exportar Relatório em PDF")
if st.button("Gerar PDF"):
    pdf_bytes = gerar_pdf(fig, fig2)
    st.download_button(
        label="📥 Baixar Relatório",
        data=pdf_bytes,
        file_name="relatorio_plano_fogo.pdf",
        mime="application/pdf"
    )














