"""Warmte, ventilatie, energie en stabiliteit. Alle aannames staan hier benoemd."""
import math
import model as m

T_IN = 11.0                   # midden van de doeltemperatuur 10-12 C
T_DESIGN = -5.0               # ontwerpnacht
PIR_R = 1.80                  # Rd IKO enertherm 40 mm, Hornbach
PLY_L, WOOD_L = 0.17, 0.13    # W/mK
UW_UP = 1.3                   # Hornbach kelderraam
RSI, RSE, RSI_DOWN = 0.13, 0.13, 0.17


def magnus(t):
    """Verzadigde waterdamp in g/m3."""
    p = 6.112 * math.exp(17.62 * t / (243.12 + t)) * 100
    return p / (461.5 * (t + 273.15)) * 1000


def stack_flow(diam_mm, t_out, h=0.85, cd=0.5):
    """Natuurlijke trek in m3/h, zonder wind. cd 0,5 houdt rekening met gaas en bochten."""
    dt = T_IN - t_out
    if dt <= 0:
        return 0.0
    dp = 1.25 * 9.81 * h * dt / (t_out + 273.15)
    v = math.sqrt(2 * dp / 1.25)
    return cd * math.pi / 4 * (diam_mm / 1000) ** 2 * v * 3600


def needed_flow(t_out, rh_out=0.9, moist=10.0, rh_in=0.75):
    """Luchtverversing (m3/h) om bij moist g/h onder rh_in te blijven."""
    margin = rh_in * magnus(T_IN) - rh_out * magnus(t_out)
    return moist / margin if margin > 0 else float("inf")


def heat():
    r_ply = m.PLY / 1000 / PLY_L
    r_ply18 = m.PLY_F / 1000 / PLY_L
    r_w44 = 0.044 / WOOD_L
    r_w69 = 0.069 / WOOD_L
    u_wall_ins = 1 / (RSI + r_ply + PIR_R + RSE)
    u_wall_wood = 1 / (RSI + r_ply + r_w44 + RSE)
    u_floor_ins = 1 / (RSI_DOWN + r_ply18 + PIR_R + 0.18 + r_ply + RSE)
    u_floor_wood = 1 / (RSI_DOWN + r_ply18 + r_w69 + r_ply + RSE)
    u_ceil_ins = 1 / (RSI + r_ply + PIR_R + RSE)
    u_ceil_wood = 1 / (RSI + r_ply + r_w69 + RSE)

    iw, id_, ih = (m.IN_X1 - m.IN_X0) / 1000, (m.IN_Y1 - m.IN_Y0) / 1000, m.ROOM_H / 1000
    stud = m.STUD_H / 1000
    a_side = id_ * ih
    a_side_pir = 2 * 0.300 * stud
    a_back = iw * ih
    a_back_pir = 4 * 0.250 * stud
    a_front = iw * ih - 0.5
    hole = (m.HOLE_X1 - m.HOLE_X0) * (m.HOLE_Y1 - m.HOLE_Y0) / 1e6
    a_floor = iw * id_ - hole
    a_floor_pir = sum((p.box[1] - p.box[0]) * (p.box[3] - p.box[2]) for p in m.parts if p.name == "PIR tussenvloer") / 1e6
    a_ceil = iw * id_
    a_ceil_pir = 4 * 0.250 * 0.732

    def h(a_tot, a_ins, ui, uw):
        return min(a_ins, a_tot) * ui + max(a_tot - a_ins, 0) * uw

    parts = {
        "Zijwanden (2x)": h(2 * a_side, 2 * a_side_pir, u_wall_ins, u_wall_wood),
        "Achterwand": h(a_back, a_back_pir, u_wall_ins, u_wall_wood),
        "Voorwand rond raam (vooral hout)": a_front * u_wall_wood,
        "Raam 100x50 (Uw 1,3)": 0.5 * UW_UP,
        "Vloer": h(a_floor, a_floor_pir, u_floor_ins, u_floor_wood),
        "Plafond": h(a_ceil, a_ceil_pir, u_ceil_ins, u_ceil_wood),
        "Trapgat (aanname: koude lucht blijft beneden)": hole * 3.0,
    }
    return dict(parts=parts, H=sum(parts.values()),
                U=dict(wall_ins=u_wall_ins, wall_wood=u_wall_wood,
                       floor_ins=u_floor_ins, ceil_ins=u_ceil_ins))


def results():
    hh = heat()
    H = hh["H"]
    q_design = needed_flow(T_DESIGN)
    dT = T_IN - T_DESIGN
    p_trans = H * dT
    p_vent = 0.34 * q_design * dT
    # winter nov-mrt, gemiddelde buitentemperatuur circa 5,5 C (aanname op basis van NL-klimaat)
    q_win = needed_flow(5.5)
    p_avg = (H + 0.34 * q_win) * (T_IN - 5.5)
    kwh_season = p_avg * 24 * 151 / 1000
    # december: gemiddeld circa 4,5 C
    q_dec = needed_flow(4.5)
    p_dec = (H + 0.34 * q_dec) * (T_IN - 4.5)
    wh_day_dec = p_dec * 24
    pv_low, pv_high = 18 / 31, 32 / 31              # kWh per kWp per dag, bronnen 18-32 kWh/kWp in december
    wp_needed = (wh_day_dec / 1000 / pv_high * 1000, wh_day_dec / 1000 / pv_low * 1000)
    battery_12v_100ah = 12.8 * 100 * 0.9             # Wh bruikbaar LiFePO4, 90 %
    batt_hours = battery_12v_100ah / p_dec

    # dagelijkse opbrengst van een paneel van 100 Wp
    pv100 = (0.1 * pv_low * 1000, 0.1 * pv_high * 1000)

    vent_rows = []
    for t in (-5, 0, 5, 10):
        vent_rows.append((t, needed_flow(t, moist=5), needed_flow(t, moist=10),
                          stack_flow(36, t), stack_flow(46, t), stack_flow(71, t)))

    # stabiliteit
    mass = m.weight()
    q_wind = 0.9       # kN/m2: stootdruk x vormfactor (aanname, ruim voor beschutte tuin)
    height = m.Z_TOP / 1000
    a_wind = 1.5 * height
    F = q_wind * a_wind
    M_over = F * (height / 2 + 0.18)
    M_stab = mass * 9.81 / 1000 * 0.41
    tension = max(M_over - M_stab, 0) / 0.75
    poer_kg = 0.3 * 0.3 * 0.5 * 2300

    # inwendige condensatie-grove controle op oppervlaktetemperatuur
    def surf(u):
        return T_IN - (T_IN - T_DESIGN) * RSI * u
    dew = None
    # dauwpunt bij 75 % RV en 11 C
    v = 0.75 * magnus(T_IN)
    for i in range(-200, 200):
        t = i / 10
        if magnus(t) >= v:
            dew = t
            break

    return dict(H=H, parts=hh["parts"], U=hh["U"], q_design=q_design, dT=dT, p_trans=p_trans,
                p_vent=p_vent, peak=p_trans + p_vent, p_avg=p_avg, kwh=kwh_season, p_dec=p_dec,
                wh_day_dec=wh_day_dec, wp_needed=wp_needed, batt_wh=battery_12v_100ah, batt_hours=batt_hours,
                pv100=pv100, vent=vent_rows, mass=mass, F=F, M_over=M_over, M_stab=M_stab, tension=tension,
                poer_kg=poer_kg, dew=dew, s_ins=surf(hh["U"]["wall_ins"]), s_wood=surf(hh["U"]["wall_wood"]),
                s_glass=surf(1.1))


if __name__ == "__main__":
    r = results()
    for k, v in r.items():
        print(k, v)
