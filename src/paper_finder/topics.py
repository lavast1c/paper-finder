"""The CIE 9702 AS syllabus taxonomy: subject-content sections 1-11.

Single source of truth for topic codes, display names, and the blurbs the
classifier prompt is built from. Multi-label: a question may belong to several
sections (a "define force, then check homogeneity" question is both s01 and s03).

Sections are from "Cambridge International AS & A Level Physics 9702 syllabus for
2025, 2026 and 2027", AS Level subject content. Section 1 already covers SI units,
errors/uncertainties and scalars/vectors, so there is no separate "chapter 0".

IMPORTANT: this module must stay stdlib-only. ``web/app.py`` imports it and the
deployed Vercel import chain is fastapi-only -- a stray ``import pymupdf`` here
would break the deploy with a confusing traceback.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Topic:
    code: str  # 's01'..'s11' -- DB key and URL token; stable forever
    number: int  # 1..11 -- syllabus section number, also display order
    name: str  # 'Waves'
    blurb: str  # what belongs here; goes verbatim into the classifier prompt
    subsections: tuple[str, ...]  # ('7.1 Progressive waves', ...) -- shown in the UI


TOPICS: tuple[Topic, ...] = (
    Topic(
        code="s01",
        number=1,
        name="Physical quantities and units",
        blurb=(
            "Numerical magnitude and unit of a physical quantity; reasonable estimates. "
            "SI base quantities and units (mass/kg, length/m, time/s, current/A, "
            "temperature/K); expressing derived units as products or quotients of base "
            "units; using base units to check the homogeneity of an equation; the "
            "prefixes pico to tera. Systematic errors (including zero errors) and random "
            "errors; the distinction between precision and accuracy; estimating the "
            "uncertainty in a derived quantity by adding absolute or percentage "
            "uncertainties. Scalars versus vectors and examples of each; adding and "
            "subtracting coplanar vectors; resolving a vector into two perpendicular "
            "components."
        ),
        subsections=(
            "1.1 Physical quantities",
            "1.2 SI units",
            "1.3 Errors and uncertainties",
            "1.4 Scalars and vectors",
        ),
    ),
    Topic(
        code="s02",
        number=2,
        name="Kinematics",
        blurb=(
            "Defining and using distance, displacement, speed, velocity and "
            "acceleration. Graphical representation of motion: displacement from the "
            "area under a velocity-time graph, velocity from the gradient of a "
            "displacement-time graph, acceleration from the gradient of a velocity-time "
            "graph. Deriving and using the equations of uniformly accelerated motion in "
            "a straight line, including free fall in a uniform gravitational field with "
            "no air resistance; an experiment to determine the acceleration of free "
            "fall. Projectile motion: uniform velocity in one direction with uniform "
            "acceleration perpendicular to it. (Air resistance and terminal velocity "
            "belong to Dynamics.)"
        ),
        subsections=("2.1 Equations of motion",),
    ),
    Topic(
        code="s03",
        number=3,
        name="Dynamics",
        blurb=(
            "Mass as resistance to change in motion. F = ma with resultant force and "
            "acceleration in the same direction. Linear momentum as mass times "
            "velocity; force as rate of change of momentum. Newton's three laws of "
            "motion. Weight as the effect of a gravitational field on a mass, "
            "W = mg. Non-uniform motion: qualitative treatment of frictional and "
            "viscous/drag forces including air resistance; motion in a uniform "
            "gravitational field with air resistance; terminal (constant) velocity. "
            "Principle of conservation of momentum; elastic and inelastic collisions in "
            "one and two dimensions; for an elastic collision total kinetic energy is "
            "conserved and relative speed of approach equals relative speed of "
            "separation; momentum is always conserved though kinetic energy need not "
            "be."
        ),
        subsections=(
            "3.1 Momentum and Newton's laws of motion",
            "3.2 Non-uniform motion",
            "3.3 Linear momentum and its conservation",
        ),
    ),
    Topic(
        code="s04",
        number=4,
        name="Forces, density and pressure",
        blurb=(
            "Turning effects: centre of gravity as the single point where weight acts; "
            "the moment of a force; a couple as a pair of forces producing rotation "
            "only; the torque of a couple. Equilibrium: the principle of moments; a "
            "system in equilibrium has no resultant force and no resultant torque; "
            "using a closed vector triangle for three coplanar forces in equilibrium. "
            "Density and pressure: defining and using density and pressure; deriving "
            "and using hydrostatic pressure change dp = rho*g*dh; upthrust as a "
            "difference in hydrostatic pressure; upthrust F = rho*g*V (Archimedes' "
            "principle)."
        ),
        subsections=(
            "4.1 Turning effects of forces",
            "4.2 Equilibrium of forces",
            "4.3 Density and pressure",
        ),
    ),
    Topic(
        code="s05",
        number=5,
        name="Work, energy and power",
        blurb=(
            "Work done = force times displacement in the direction of the force. "
            "Principle of conservation of energy. Efficiency as useful energy output "
            "over total energy input, and problems using it. Power as work done per "
            "unit time, P = W/t; deriving and using P = Fv. Deriving dEp = mg*dh for "
            "gravitational potential energy change in a uniform field and Ek = "
            "(1/2)mv^2 for kinetic energy, and using both, including "
            "gravitational-to-kinetic energy transformations. (Elastic potential "
            "energy stored in a deformed material belongs to Deformation of solids.)"
        ),
        subsections=(
            "5.1 Energy conservation",
            "5.2 Gravitational potential energy and kinetic energy",
        ),
    ),
    Topic(
        code="s06",
        number=6,
        name="Deformation of solids",
        blurb=(
            "Tensile and compressive forces causing deformation (one dimension only). "
            "Load, extension, compression and the limit of proportionality; Hooke's "
            "law; spring constant k = F/x. Stress, strain and the Young modulus; an "
            "experiment to determine the Young modulus of a metal wire. Elastic and "
            "plastic deformation and the elastic limit; the area under a "
            "force-extension graph as work done; elastic potential energy "
            "Ep = (1/2)Fx = (1/2)kx^2 for a material within its limit of "
            "proportionality."
        ),
        subsections=(
            "6.1 Stress and strain",
            "6.2 Elastic and plastic behaviour",
        ),
    ),
    Topic(
        code="s07",
        number=7,
        name="Waves",
        blurb=(
            "Wave motion illustrated by ropes, springs and ripple tanks. Displacement, "
            "amplitude, phase difference, period, frequency, wavelength and speed; "
            "using a cathode-ray oscilloscope time-base and y-gain to find frequency "
            "and amplitude. Deriving and using v = f*lambda. Energy transfer by a "
            "progressive wave; intensity = power/area and intensity proportional to "
            "amplitude squared. Comparing transverse and longitudinal waves and their "
            "graphs. Doppler effect for a moving source of sound: fo = fs*v/(v +/- "
            "vs). The electromagnetic spectrum: all transverse, same speed c in free "
            "space; approximate wavelength ranges from radio to gamma; visible range "
            "400-700 nm. Polarisation as a property of transverse waves; Malus's law "
            "I = I0*cos^2(theta)."
        ),
        subsections=(
            "7.1 Progressive waves",
            "7.2 Transverse and longitudinal waves",
            "7.3 Doppler effect for sound waves",
            "7.4 Electromagnetic spectrum",
            "7.5 Polarisation",
        ),
    ),
    Topic(
        code="s08",
        number=8,
        name="Superposition",
        blurb=(
            "Principle of superposition. Stationary waves on stretched strings, in air "
            "columns and with microwaves; nodes and antinodes; determining wavelength "
            "from node/antinode positions. Diffraction and the effect of gap width "
            "relative to wavelength (e.g. water waves in a ripple tank). Interference "
            "and coherence; two-source interference with water waves, sound, light and "
            "microwaves; conditions for observable fringes; double-slit "
            "lambda = a*x/D. The diffraction grating: d*sin(theta) = n*lambda and its "
            "use to determine the wavelength of light."
        ),
        subsections=(
            "8.1 Stationary waves",
            "8.2 Diffraction",
            "8.3 Interference",
            "8.4 The diffraction grating",
        ),
    ),
    Topic(
        code="s09",
        number=9,
        name="Electricity",
        blurb=(
            "Electric current as a flow of charge carriers; quantised charge; "
            "Q = I*t; I = Anvq for a current-carrying conductor. Potential difference "
            "as energy transferred per unit charge, V = W/Q; electrical power "
            "P = VI = I^2*R = V^2/R. Defining resistance; V = IR; Ohm's law; the I-V "
            "characteristics of a metallic conductor, a semiconductor diode and a "
            "filament lamp, and why a filament lamp's resistance rises with current. "
            "Resistivity R = rho*L/A. How the resistance of an LDR falls with light "
            "intensity and of a thermistor falls with temperature. (Circuits with "
            "e.m.f., internal resistance, Kirchhoff's laws or potential dividers "
            "belong to D.C. circuits.)"
        ),
        subsections=(
            "9.1 Electric current",
            "9.2 Potential difference and power",
            "9.3 Resistance and resistivity",
        ),
    ),
    Topic(
        code="s10",
        number=10,
        name="D.C. circuits",
        blurb=(
            "Circuit symbols and diagrams. Electromotive force as energy transferred "
            "per unit charge in driving charge around a complete circuit; distinguishing "
            "e.m.f. from potential difference; the effect of internal resistance on "
            "terminal p.d. Kirchhoff's first law (conservation of charge) and second "
            "law (conservation of energy); deriving and using the combined resistance "
            "of resistors in series and in parallel; solving circuit problems with "
            "Kirchhoff's laws. Potential divider circuits; the potentiometer for "
            "comparing potential differences; galvanometers in null methods; "
            "thermistors and LDRs in potential dividers."
        ),
        subsections=(
            "10.1 Practical circuits",
            "10.2 Kirchhoff's laws",
            "10.3 Potential dividers",
        ),
    ),
    Topic(
        code="s11",
        number=11,
        name="Particle physics",
        blurb=(
            "The alpha-particle scattering experiment and the small, massive nucleus; "
            "the nuclear atom of protons, neutrons and orbital electrons; nucleon "
            "number and proton number; isotopes; nuclide notation; conservation of "
            "nucleon number and charge in nuclear processes. Composition, mass and "
            "charge of alpha, beta-minus, beta-plus and gamma radiation; antiparticles "
            "and the positron; (anti)neutrinos in beta decay and the continuous beta "
            "energy spectrum; radioactive decay equations; the unified atomic mass "
            "unit. Fundamental particles: the six quark flavours and their charges; "
            "protons and neutrons as quark combinations; hadrons as baryons or mesons; "
            "quark changes in beta decay; leptons (electrons and neutrinos)."
        ),
        subsections=(
            "11.1 Atoms, nuclei and radiation",
            "11.2 Fundamental particles",
        ),
    ),
)

BY_CODE: dict[str, Topic] = {t.code: t for t in TOPICS}
CODES: frozenset[str] = frozenset(BY_CODE)
