"""CIE syllabus taxonomies -- one per (subject, paper group) the corpus covers.

Single source of truth for topic codes, display names, and the blurbs the
classifier prompt is built from. Multi-label: a question may belong to several
sections (a "define force, then check homogeneity" question is both s01 and s03).

Six taxonomies today:

* ``PHYSICS`` -- 9702 Papers 1 & 2, sections ``s01``..``s11``, from "Cambridge
  International AS & A Level Physics 9702 syllabus for 2025, 2026 and 2027".
* ``FURTHER_PURE_1`` -- 9231 Paper 1 (Further Pure Mathematics 1), ``fp1``..``fp7``.
* ``FURTHER_PROB_STATS`` -- 9231 Paper 4 (Further Probability & Statistics),
  ``fs1``..``fs5``.
* ``PURE_MATH_1`` -- 9709 Paper 1 (Pure Mathematics 1), ``pm1``..``pm8``.
* ``PROB_STATS_1`` -- 9709 Paper 5 (Probability & Statistics 1), ``ps1``..``ps5``.
* ``CHEMISTRY`` -- 9701 Papers 1 & 2, sections ``ch01``..``ch22``, from
  "Cambridge International AS & A Level Chemistry 9701 syllabus for 2025, 2026
  and 2027" (AS Level subject content, pp.16-38). Like ``PHYSICS``, one
  taxonomy spans both papers -- P1 (MCQ) and P2 (structured) both examine the
  same full AS syllabus, unlike 9231/9709's disjoint-content paper splits.

Codes are namespaced per taxonomy so they never collide in the ``topics`` table,
``question_topics``, ``labels/question_topics.tsv`` or the ``?topics=`` URL token.
Use :func:`taxonomy_for` (from a filename's subject code + paper number) or
:func:`taxonomy_by_name` (from ``papers.subject_name``) to pick the right one.

IMPORTANT: this module must stay stdlib-only. ``web/app.py`` imports it and the
deployed Vercel import chain is fastapi-only -- a stray ``import pymupdf`` here
would break the deploy with a confusing traceback.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Topic:
    code: str  # e.g. 's07' / 'fp4' -- DB key and URL token; stable forever
    number: int  # syllabus section number within its taxonomy, also display order
    name: str  # 'Waves'
    blurb: str  # what belongs here; goes verbatim into the classifier prompt
    subsections: tuple[str, ...]  # ('7.1 Progressive waves', ...) -- shown in the UI


@dataclass(frozen=True)
class Taxonomy:
    """One syllabus's section list, tied to the subject + papers it labels."""

    key: str  # stable id: '9702' / '9231p1' / '9231p4'
    subject_code: str  # CIE code from the filename: '9702' / '9231'
    papers: tuple[int, ...]  # paper numbers this taxonomy applies to
    subject_name: str  # matches papers.subject_name (the UI's Subject value)
    topics: tuple[Topic, ...]

    @property
    def codes(self) -> frozenset[str]:
        return frozenset(t.code for t in self.topics)

    @property
    def by_code(self) -> dict[str, Topic]:
        return {t.code: t for t in self.topics}


_PHYSICS_TOPICS: tuple[Topic, ...] = (
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

# --- 9231 Paper 1: Further Pure Mathematics 1 (syllabus section 1) -------------

_FURTHER_PURE_1_TOPICS: tuple[Topic, ...] = (
    Topic(
        code="fp1",
        number=1,
        name="Roots of polynomial equations",
        blurb=(
            "Relations between the roots and coefficients of a polynomial equation of "
            "degree 2, 3 or 4: sums and products of roots and symmetric functions of the "
            "roots such as the sum of the squares or the sum of the reciprocals. Using "
            "these relations to evaluate expressions in the roots or to find unknown "
            "coefficients. Forming a new equation whose roots are a given function of the "
            "original roots (reciprocals, squares, or a linear function of the old roots) "
            "by means of a substitution."
        ),
        subsections=("1.1 Roots of polynomial equations",),
    ),
    Topic(
        code="fp2",
        number=2,
        name="Rational functions and graphs",
        blurb=(
            "Sketching graphs of rational functions where the numerator and denominator "
            "have degree at most 2, including finding vertical, horizontal and oblique "
            "asymptotes, turning points and intersections with the axes, and determining "
            "the set of values the function can take (e.g. using a discriminant). "
            "Understanding and using the relationships between the graphs of y = f(x), "
            "y^2 = f(x), y = 1/f(x), y = |f(x)| and y = f(|x|), including using such "
            "sketches when solving equations or inequalities."
        ),
        subsections=("1.2 Rational functions and graphs",),
    ),
    Topic(
        code="fp3",
        number=3,
        name="Summation of series",
        blurb=(
            "Using the standard results for the sums of r, r^2 and r^3 to find related "
            "finite sums. The method of differences to sum a finite series, including "
            "using partial fractions to write the general term in a telescoping form. "
            "Recognising by direct consideration of a sum to n terms when a series is "
            "convergent, and finding the sum to infinity in such cases."
        ),
        subsections=("1.3 Summation of series",),
    ),
    Topic(
        code="fp4",
        number=4,
        name="Matrices",
        blurb=(
            "Addition, subtraction and multiplication of matrices with at most 3 rows and "
            "columns (including non-square matrices); the zero and identity matrices. "
            "Singular and non-singular square matrices; evaluating 2x2 and 3x3 "
            "determinants and finding inverses of non-singular matrices; the result "
            "(AB)^-1 = B^-1 A^-1. Using 2x2 matrices to represent geometric "
            "transformations of the x-y plane (rotation, reflection, enlargement, stretch, "
            "shear), the product AB as a composition of transformations, the relationship "
            "between A and its inverse, and the determinant as the area scale factor. "
            "Invariant points and invariant lines of a transformation represented by a "
            "matrix."
        ),
        subsections=("1.4 Matrices",),
    ),
    Topic(
        code="fp5",
        number=5,
        name="Polar coordinates",
        blurb=(
            "The relations between Cartesian and polar coordinates (with r >= 0) and "
            "converting equations of curves between Cartesian and polar form. Sketching "
            "simple polar curves for a suitable interval of theta, showing symmetry, "
            "intersections with the initial line, the form of the curve at the pole and "
            "least or greatest values of r. Recalling and using the formula (1/2) integral "
            "of r^2 with respect to theta for the area of a sector."
        ),
        subsections=("1.5 Polar coordinates",),
    ),
    Topic(
        code="fp6",
        number=6,
        name="Vectors",
        blurb=(
            "The equation of a plane in the forms ax + by + cz = d, r.n = p and "
            "r = a + lambda b + mu c, and converting between them. The vector (cross) "
            "product of two vectors, expressed as |a||b| sin(theta) n-hat or in component "
            "form. Using lines and planes together with scalar and vector products to "
            "solve problems about distances, angles and intersections: whether a line lies "
            "in, is parallel to, or meets a plane and the point of intersection; the foot "
            "of the perpendicular from a point to a plane; the angle between a line and a "
            "plane and between two planes; the line of intersection of two planes; the "
            "shortest distance between two skew lines and the common perpendicular to them."
        ),
        subsections=("1.6 Vectors",),
    ),
    Topic(
        code="fp7",
        number=7,
        name="Proof by induction",
        blurb=(
            "Using the method of mathematical induction to establish a given result -- for "
            "example a formula for a sum to n terms, a closed form for a recurrently "
            "defined sequence, a formula for the nth power of a matrix, or a divisibility "
            "result. Recognising situations where a conjecture based on a limited trial "
            "followed by inductive proof is a useful strategy, and carrying this out in "
            "simple cases such as finding an nth derivative or the value of a product."
        ),
        subsections=("1.7 Proof by induction",),
    ),
)

# --- 9231 Paper 4: Further Probability & Statistics (syllabus section 4) -------

_FURTHER_PROB_STATS_TOPICS: tuple[Topic, ...] = (
    Topic(
        code="fs1",
        number=1,
        name="Continuous random variables",
        blurb=(
            "Probability density functions, which may be defined piecewise, and the "
            "general result E(g(X)) = integral of g(x) f(x). The relationship between the "
            "probability density function (PDF) and the cumulative distribution function "
            "(CDF), using either to evaluate probabilities or percentiles. Using the CDF "
            "of one variable to find the CDF, and hence PDF, of a related variable such as "
            "Y = X^3."
        ),
        subsections=("4.1 Continuous random variables",),
    ),
    Topic(
        code="fs2",
        number=2,
        name="Inference using normal and t-distributions",
        blurb=(
            "Formulating hypotheses and carrying out a t-test on a population mean from a "
            "small sample of a normal population with unknown variance. Calculating a "
            "pooled estimate of a population variance from two samples. Testing the "
            "difference of two population means with a 2-sample t-test, a paired-sample "
            "t-test, or a test using a normal distribution, and selecting the appropriate "
            "test. Confidence intervals for a population mean, and for a difference of "
            "means, using a t-distribution or a normal distribution as appropriate."
        ),
        subsections=("4.2 Inference using normal and t-distributions",),
    ),
    Topic(
        code="fs3",
        number=3,
        name="Chi-squared tests",
        blurb=(
            "Fitting a theoretical distribution prescribed by a given hypothesis to data "
            "and carrying out a chi-squared goodness-of-fit test with the appropriate "
            "number of degrees of freedom, combining classes so that each expected "
            "frequency is at least 5. Using a chi-squared test with the appropriate "
            "degrees of freedom for independence in a contingency table (Yates' correction "
            "not required), combining rows or columns so that each expected cell frequency "
            "is at least 5."
        ),
        subsections=("4.3 Chi-squared tests",),
    ),
    Topic(
        code="fs4",
        number=4,
        name="Non-parametric tests",
        blurb=(
            "The idea of a non-parametric test and situations in which one is useful, such "
            "as sampling from a population that cannot be assumed normal. The basis of the "
            "sign test, the Wilcoxon signed-rank test and the Wilcoxon rank-sum test (the "
            "Wilcoxon tests being valid only for symmetrical distributions). Single-sample "
            "sign and Wilcoxon signed-rank tests for a population median, and "
            "paired-sample sign, Wilcoxon matched-pairs signed-rank and Wilcoxon rank-sum "
            "tests for the identity of two populations, including normal approximations."
        ),
        subsections=("4.4 Non-parametric tests",),
    ),
    Topic(
        code="fs5",
        number=5,
        name="Probability generating functions",
        blurb=(
            "The concept of a probability generating function (PGF); constructing and "
            "using the PGF for the discrete uniform, binomial, geometric and Poisson "
            "distributions. Using formulae for the mean and variance of a discrete random "
            "variable in terms of its PGF. Using the result that the PGF of a sum of "
            "independent random variables is the product of their PGFs."
        ),
        subsections=("4.5 Probability generating functions",),
    ),
)


# --- 9709 Paper 1: Pure Mathematics 1 (syllabus section 1) --------------------

_PURE_MATH_1_TOPICS: tuple[Topic, ...] = (
    Topic(
        code="pm1",
        number=1,
        name="Quadratics",
        blurb=(
            "Completing the square for a quadratic polynomial ax^2 + bx + c and using "
            "the completed-square form, e.g. to locate the vertex or sketch the graph. "
            "Finding and using the discriminant to determine the number of real roots of "
            "ax^2 + bx + c = 0 (including repeated roots). Solving quadratic equations "
            "and quadratic inequalities in one unknown by factorising, completing the "
            "square or the formula. Solving by substitution a pair of simultaneous "
            "equations of which one is linear and one is quadratic. Recognising and "
            "solving equations that are quadratic in some function of x, e.g. "
            "x^4 - 5x^2 + 4 = 0 or equations quadratic in sqrt(x) or in tan x."
        ),
        subsections=("1.1 Quadratics",),
    ),
    Topic(
        code="pm2",
        number=2,
        name="Functions",
        blurb=(
            "The terms function, domain, range, one-one function, inverse function and "
            "composition of functions. Finding the range of a given function and the "
            "composition of two functions, including that a composite function gf can "
            "only be formed when the range of f lies within the domain of g. Deciding "
            "whether a function is one-one and finding the inverse of a one-one function "
            "in simple cases. The graphical relationship between a one-one function and "
            "its inverse, with the mirror line y = x. The transformations of the graph "
            "of y = f(x) given by y = f(x) + a, y = f(x + a), y = af(x), y = f(ax) and "
            "simple combinations of these, using the terms translation, reflection and "
            "stretch."
        ),
        subsections=("1.2 Functions",),
    ),
    Topic(
        code="pm3",
        number=3,
        name="Coordinate geometry",
        blurb=(
            "The equation of a straight line given sufficient information (two points, "
            "or a point and the gradient); the forms y = mx + c, y - y1 = m(x - x1) and "
            "ax + by + c = 0, with distances, gradients, midpoints, points of "
            "intersection, and the gradient relationship between parallel and "
            "perpendicular lines. The circle (x - a)^2 + (y - b)^2 = r^2 with centre "
            "(a, b) and radius r, and the expanded form x^2 + y^2 + 2gx + 2fy + c = 0. "
            "Algebraic methods for problems involving lines and circles, including "
            "elementary circle properties (tangent perpendicular to radius, angle in a "
            "semicircle, symmetry). Using the relationship between points of "
            "intersection of graphs and solutions of equations, e.g. the set of values "
            "of k for which a line meets, touches or misses a curve."
        ),
        subsections=("1.3 Coordinate geometry",),
    ),
    Topic(
        code="pm4",
        number=4,
        name="Circular measure",
        blurb=(
            "The definition of a radian and the relationship between radians and "
            "degrees. Using the formulae s = r*theta for arc length and A = (1/2)*r^2*theta "
            "for sector area in solving problems, including the calculation of lengths "
            "and angles in triangles and the areas of triangles."
        ),
        subsections=("1.4 Circular measure",),
    ),
    Topic(
        code="pm5",
        number=5,
        name="Trigonometry",
        blurb=(
            "Sketching and using the graphs of sine, cosine and tangent for angles of "
            "any size, in degrees or radians, e.g. y = 3 sin x, y = 1 - cos 2x, "
            "y = tan(x + pi/4). The exact values of the sine, cosine and tangent of "
            "30, 45, 60 degrees and related angles. The notations sin^-1, cos^-1, "
            "tan^-1 for principal values. Using the identities tan(theta) = "
            "sin(theta)/cos(theta) and sin^2(theta) + cos^2(theta) = 1 to prove "
            "identities, simplify expressions and solve equations. Finding all "
            "solutions of a simple trigonometric equation lying in a specified interval."
        ),
        subsections=("1.5 Trigonometry",),
    ),
    Topic(
        code="pm6",
        number=6,
        name="Series",
        blurb=(
            "The expansion of (a + b)^n where n is a positive integer, with the "
            "notations nCr and n!. Recognising arithmetic and geometric progressions "
            "and using the formulae for the nth term and the sum of the first n terms "
            "(a, b, c are in arithmetic progression if 2b = a + c and in geometric "
            "progression if b^2 = ac). The condition for convergence of a geometric "
            "progression and the formula for the sum to infinity of a convergent "
            "geometric progression."
        ),
        subsections=("1.6 Series",),
    ),
    Topic(
        code="pm7",
        number=7,
        name="Differentiation",
        blurb=(
            "The gradient of a curve at a point as the limit of the gradients of a "
            "sequence of chords; the notations f'(x), f''(x), dy/dx and d^2y/dx^2. The "
            "derivative of x^n for any rational n, with constant multiples, sums and "
            "differences, and the chain rule for composite functions. Applying "
            "differentiation to gradients, tangents and normals, increasing and "
            "decreasing functions, and connected rates of change. Locating stationary "
            "points and determining their nature (including using the second "
            "derivative), and using information about stationary points when sketching "
            "graphs."
        ),
        subsections=("1.7 Differentiation",),
    ),
    Topic(
        code="pm8",
        number=8,
        name="Integration",
        blurb=(
            "Integration as the reverse of differentiation; integrating (ax + b)^n for "
            "any rational n except -1, with constant multiples, sums and differences. "
            "Finding a constant of integration, e.g. the equation of a curve through a "
            "given point. Evaluating definite integrals, including simple improper "
            "integrals. Using definite integration to find the area of a region bounded "
            "by a curve and lines parallel to the axes, between a curve and a line or "
            "between two curves, and to find a volume of revolution about the x- or "
            "y-axis."
        ),
        subsections=("1.8 Integration",),
    ),
)

# --- 9709 Paper 5: Probability & Statistics 1 (syllabus section 5) ------------

_PROB_STATS_1_TOPICS: tuple[Topic, ...] = (
    Topic(
        code="ps1",
        number=1,
        name="Representation of data",
        blurb=(
            "Selecting a suitable way to present raw statistical data and discussing "
            "the advantages or disadvantages of particular representations. Drawing and "
            "interpreting stem-and-leaf diagrams (including back-to-back), "
            "box-and-whisker plots, histograms and cumulative frequency graphs. "
            "Measures of central tendency (mean, median, mode) and variation (range, "
            "interquartile range, standard deviation), used to compare and contrast "
            "data sets. Using a cumulative frequency graph to estimate medians, "
            "quartiles, percentiles and the proportion of a distribution above or below "
            "a value. Calculating the mean and standard deviation of a set of data "
            "(including grouped data) from the data itself or from totals such as "
            "sum x and sum x^2, or coded totals sum (x - a) and sum (x - a)^2, for up "
            "to two data sets."
        ),
        subsections=("5.1 Representation of data",),
    ),
    Topic(
        code="ps2",
        number=2,
        name="Permutations and combinations",
        blurb=(
            "The terms permutation and combination and simple problems involving "
            "selections. Solving problems about arrangements of objects in a line, "
            "including those involving repetition (e.g. the number of ways of arranging "
            "the letters of a word with repeated letters) and restriction (e.g. "
            "arrangements in which two particular people must, or must not, be next to "
            "each other), and cases such as people sitting in two or more rows. "
            "Arrangements of objects in a circle are not included."
        ),
        subsections=("5.2 Permutations and combinations",),
    ),
    Topic(
        code="ps3",
        number=3,
        name="Probability",
        blurb=(
            "Evaluating probabilities by enumerating equiprobable elementary events or "
            "by calculation using permutations and combinations. Addition and "
            "multiplication of probabilities in simple cases. The meaning of exclusive "
            "and independent events, including deciding whether A and B are independent "
            "by comparing P(A and B) with P(A) * P(B). Calculating and using "
            "conditional probabilities in simple cases, e.g. with a sample space of "
            "equiprobable events or a tree diagram, using "
            "P(A and B) = P(A | B) * P(B)."
        ),
        subsections=("5.3 Probability",),
    ),
    Topic(
        code="ps4",
        number=4,
        name="Discrete random variables",
        blurb=(
            "Drawing up a probability distribution table for a discrete random variable "
            "X and calculating E(X) and Var(X). The binomial distribution B(n, p) and "
            "the geometric distribution Geo(p), recognising practical situations where "
            "each is a suitable model, and the formulae for their probabilities. The "
            "formulae for the expectation and variance of the binomial distribution and "
            "for the expectation of the geometric distribution."
        ),
        subsections=("5.4 Discrete random variables",),
    ),
    Topic(
        code="ps5",
        number=5,
        name="The normal distribution",
        blurb=(
            "Using a normal distribution to model a continuous random variable and "
            "using normal distribution tables, including sketches of normal curves. For "
            "X ~ N(mu, sigma^2): finding P(X > x1) or a related probability given x1, "
            "mu and sigma, or finding a relationship between x1, mu and sigma given "
            "such a probability, showing full standardisation working "
            "Z = (X - mu) / sigma. The conditions under which the normal distribution "
            "is a suitable approximation to the binomial distribution (np > 5 and "
            "nq > 5), and using this approximation with a continuity correction."
        ),
        subsections=("5.5 The normal distribution",),
    ),
)


# --- 9701 Papers 1 & 2: Chemistry (AS Level syllabus sections 1-22) -----------

_CHEMISTRY_TOPICS: tuple[Topic, ...] = (
    Topic(
        code="ch01",
        number=1,
        name="Atomic structure",
        blurb=(
            "Protons, neutrons and electrons: relative charges and relative masses; "
            "the distribution of mass and charge within an atom; atomic/proton number "
            "and mass/nucleon number; deducing the numbers of protons, neutrons and "
            "electrons in an atom or ion; the behaviour of beams of protons, neutrons "
            "and electrons moving at the same velocity in an electric field; trends in "
            "atomic and ionic radius across a period and down a group. Isotopes: same "
            "chemical properties, different physical properties (mass, density). "
            "Shells, sub-shells and orbitals; the principal quantum number n; the "
            "number of orbitals and electrons s, p and d sub-shells hold; the aufbau "
            "order of sub-shells within the first three shells plus 4s and 4p; full and "
            "noble-gas-shorthand electronic configurations of atoms and ions (e.g. Fe: "
            "1s2 2s2 2p6 3s2 3p6 3d6 4s2 or [Ar] 3d6 4s2) and electrons-in-boxes "
            "notation; shapes of s and p orbitals; a free radical as a species with one "
            "or more unpaired electrons. First, second and successive ionisation "
            "energies: constructing the defining equations; trends across a period and "
            "down a group, and the variation in successive values for one element; "
            "explaining ionisation energy from nuclear charge, atomic/ionic radius, "
            "shielding and spin-pair repulsion; deducing an element's electronic "
            "configuration or Periodic Table position from successive ionisation "
            "energy data."
        ),
        subsections=(
            "1.1 Particles in the atom and atomic radius",
            "1.2 Isotopes",
            "1.3 Electrons, energy levels and atomic orbitals",
            "1.4 Ionisation energy",
        ),
    ),
    Topic(
        code="ch02",
        number=2,
        name="Atoms, molecules and stoichiometry",
        blurb=(
            "The unified atomic mass unit; relative atomic, isotopic, molecular and "
            "formula mass defined in terms of it; the mole and the Avogadro constant. "
            "Writing formulas of ionic compounds from ionic charge/oxidation number "
            "(predicted from Periodic Table position, or recalled for common "
            "polyatomic ions such as NO3-, CO3 2-, SO4 2-, OH-, NH4+, HCO3- and PO4 "
            "3-); writing and balancing equations, including ionic equations with "
            "spectator ions removed, and state symbols; empirical versus molecular "
            "formula; anhydrous, hydrated and water of crystallisation; calculating "
            "empirical/molecular formulas from data. Mole calculations covering "
            "reacting masses (including percentage yield), gas volumes, volumes and "
            "concentrations of solutions, limiting and excess reagent, and deducing "
            "stoichiometric relationships from such calculations."
        ),
        subsections=(
            "2.1 Relative masses of atoms and molecules",
            "2.2 The mole and the Avogadro constant",
            "2.3 Formulas",
            "2.4 Reacting masses and volumes (of solutions and gases)",
        ),
    ),
    Topic(
        code="ch03",
        number=3,
        name="Chemical bonding",
        blurb=(
            "Electronegativity: definition, the factors behind its trends (nuclear "
            "charge, atomic radius, shielding), and using electronegativity "
            "differences to predict ionic versus covalent bonding. Ionic bonding "
            "(sodium chloride, magnesium oxide, calcium fluoride) and metallic bonding "
            "as electrostatic attractions. Covalent and coordinate (dative covalent) "
            "bonding in named molecules (H2, O2, N2, Cl2, HCl, CO2, NH3, CH4, C2H6, "
            "C2H4), expanded octets in Period 3 compounds (SO2, PCl5, SF6), and dative "
            "bonding in NH4+ and Al2Cl6; sigma bonds from direct orbital overlap and pi "
            "bonds from sideways p-orbital overlap, described for H2, C2H6, C2H4, HCN "
            "and N2; sp, sp2 and sp3 hybridisation; bond energy and bond length used to "
            "compare reactivity. VSEPR shapes and bond angles for BF3, CO2, CH4, NH3, "
            "H2O, SF6 and PF5, and predicting the shapes of analogous molecules/ions. "
            "Hydrogen bonding limited to N-H and O-H groups (ammonia, water) and the "
            "anomalous properties of ice/water it explains (high melting/boiling point, "
            "high surface tension, ice less dense than water); bond polarity and dipole "
            "moments from electronegativity; van der Waals' forces as the generic term "
            "for intermolecular forces, split into instantaneous dipole-induced dipole "
            "(London dispersion) and permanent dipole-permanent dipole forces "
            "(hydrogen bonding being a special, stronger case of the latter); ionic, "
            "covalent and metallic bonds all being stronger than intermolecular forces. "
            "Dot-and-cross diagrams for ionic, covalent and coordinate bonding, "
            "including expanded-octet and odd-electron species. (Reaction mechanisms "
            "that use curly arrows belong to organic chemistry's characteristic "
            "reactions, not here.)"
        ),
        subsections=(
            "3.1 Electronegativity and bonding",
            "3.2 Ionic bonding",
            "3.3 Metallic bonding",
            "3.4 Covalent bonding and coordinate (dative covalent) bonding",
            "3.5 Shapes of molecules",
            "3.6 Intermolecular forces, electronegativity and bond properties",
            "3.7 Dot-and-cross diagrams",
        ),
    ),
    Topic(
        code="ch04",
        number=4,
        name="States of matter",
        blurb=(
            "The kinetic-theory origin of gas pressure as collisions between gas "
            "molecules and the container wall; the ideal-gas assumptions of zero "
            "particle volume and no intermolecular forces; using pV = nRT, including "
            "to find Mr. Lattice structures: giant ionic (sodium chloride, magnesium "
            "oxide), simple molecular (iodine, buckminsterfullerene C60, ice), giant "
            "molecular (silicon(IV) oxide, graphite, diamond) and giant metallic "
            "(copper); relating structure/bonding type to melting point, boiling "
            "point, electrical conductivity and solubility, and deducing the structure "
            "and bonding present in a substance from given data."
        ),
        subsections=(
            "4.1 The gaseous state: ideal and real gases and pV = nRT",
            "4.2 Bonding and structure",
        ),
    ),
    Topic(
        code="ch05",
        number=5,
        name="Chemical energetics",
        blurb=(
            "Exothermic (delta H negative) and endothermic (delta H positive) "
            "reactions; constructing and interpreting a reaction pathway (energy "
            "profile) diagram showing enthalpy change and activation energy; standard "
            "conditions (298 K, 101 kPa); enthalpy change of reaction, formation, "
            "combustion and neutralisation. Energy transfer as bond breaking "
            "(endothermic) and bond making (exothermic); using bond energies (some "
            "exact, most average) to calculate delta Hr; calculating enthalpy changes "
            "from experimental results via q = mc delta T and delta H = -mc delta T / "
            "n. Hess's law energy cycles, including using bond energy data, to find "
            "enthalpy changes that cannot be measured directly."
        ),
        subsections=(
            "5.1 Enthalpy change, delta H",
            "5.2 Hess's law",
        ),
    ),
    Topic(
        code="ch06",
        number=6,
        name="Electrochemistry",
        blurb=(
            "Calculating oxidation numbers of elements in compounds and ions, and "
            "using changes in oxidation number to balance equations; redox, "
            "oxidation, reduction and disproportionation explained in terms of "
            "electron transfer and oxidation-number change; oxidising agent and "
            "reducing agent; the Roman-numeral convention for the magnitude of an "
            "oxidation number."
        ),
        subsections=(
            "6.1 Redox processes: electron transfer and changes in oxidation number "
            "(oxidation state)",
        ),
    ),
    Topic(
        code="ch07",
        number=7,
        name="Equilibria",
        blurb=(
            "Reversible reactions and dynamic equilibrium (equal forward/reverse "
            "rates, constant concentrations) requiring a closed system; Le "
            "Chatelier's principle and using it to predict qualitatively the effect "
            "of temperature, concentration, pressure or a catalyst on a system at "
            "equilibrium; deducing Kc (concentrations) and Kp (partial pressures, "
            "mole fraction) expressions and using them in calculations (no "
            "quadratics) including quantities present at equilibrium; which of these "
            "changes alter the value of the equilibrium constant itself, as distinct "
            "from just shifting the position of equilibrium; the Haber and Contact "
            "processes as industrial applications. Bronsted-Lowry acid/base theory; "
            "the common acids (HCl, H2SO4, HNO3, CH3COOH) and alkalis (NaOH, KOH, "
            "NH3); strong acids/bases as fully dissociated versus weak acids/bases as "
            "partially dissociated, and the qualitative differences in their behaviour "
            "(reaction with a reactive metal, pH by meter/indicator/conductivity); the "
            "pH scale (7 = neutral); neutralisation as H+(aq) + OH-(aq) -> H2O(l) "
            "forming a salt; sketching pH titration curves for strong/weak acid-alkali "
            "combinations and selecting a suitable indicator. (Enthalpy change of "
            "neutralisation is measured the same way experimentally but belongs to "
            "Chemical energetics, not here.)"
        ),
        subsections=(
            "7.1 Chemical equilibria: reversible reactions, dynamic equilibrium",
            "7.2 Bronsted-Lowry theory of acids and bases",
        ),
    ),
    Topic(
        code="ch08",
        number=8,
        name="Reaction kinetics",
        blurb=(
            "Rate of reaction in terms of frequency of collisions and the "
            "distinction between effective and non-effective collisions; the "
            "qualitative effect of concentration and pressure changes on rate; "
            "calculating rate from experimental data. Activation energy, EA, as the "
            "minimum energy for an effective collision; sketching and using the "
            "Boltzmann distribution to explain why raising temperature increases the "
            "proportion of molecules with EA or more, and so the rate. Catalysts "
            "providing an alternative mechanism of lower activation energy, explained "
            "via the Boltzmann distribution and via a reaction pathway diagram drawn "
            "with and without an effective catalyst."
        ),
        subsections=(
            "8.1 Rate of reaction",
            "8.2 Effect of temperature on reaction rates and the concept of activation energy",
            "8.3 Homogeneous and heterogeneous catalysts",
        ),
    ),
    Topic(
        code="ch09",
        number=9,
        name="The Periodic Table: chemical periodicity",
        blurb=(
            "Period 3 trends in atomic radius, ionic radius, melting point and "
            "electrical conductivity, explained via structure and bonding. Reactions "
            "of the Period 3 elements with oxygen (to Na2O, MgO, Al2O3, P4O10, SO2), "
            "chlorine (to NaCl, MgCl2, AlCl3, SiCl4, PCl5) and water (Na and Mg only); "
            "the trend in oxidation number of these oxides and chlorides from their "
            "valence electrons; reactions (if any) of the oxides and chlorides with "
            "water and the resulting solution pH; acid/base behaviour of the oxides "
            "and of NaOH/Mg(OH)2/Al(OH)3, including the amphoteric behaviour of "
            "Al2O3/Al(OH)3 with both acids and (sodium hydroxide only) bases; "
            "explaining these trends via bonding and electronegativity, and "
            "suggesting the bonding type present from observed properties. Predicting "
            "the properties of an element from its group, and deducing an unknown "
            "element's nature and possible Periodic Table position from given "
            "physical/chemical data."
        ),
        subsections=(
            "9.1 Periodicity of physical properties of the elements in Period 3",
            "9.2 Periodicity of chemical properties of the elements in Period 3",
            "9.3 Chemical periodicity of other elements",
        ),
    ),
    Topic(
        code="ch10",
        number=10,
        name="Group 2",
        blurb=(
            "Reactions of the Group 2 elements magnesium to barium with oxygen, "
            "water and dilute hydrochloric/sulfuric acid; reactions of their oxides, "
            "hydroxides and carbonates with water and with dilute acids; the trend in "
            "thermal stability shown by thermal decomposition of the nitrates and "
            "carbonates down the group; predicting the trends in physical and "
            "chemical properties of the elements and these compounds down the group; "
            "the variation in solubility of the hydroxides (increasing down the "
            "group) and sulfates (decreasing down the group)."
        ),
        subsections=(
            "10.1 Similarities and trends in the properties of the Group 2 metals, "
            "magnesium to barium, and their compounds",
        ),
    ),
    Topic(
        code="ch11",
        number=11,
        name="Group 17",
        blurb=(
            "Colours and the trend in volatility of chlorine, bromine and iodine, "
            "interpreted via increasing instantaneous dipole-induced dipole forces "
            "down the group; the trend in halogen-halogen bond strength. Relative "
            "reactivity of the elements as oxidising agents, including their "
            "reactions with hydrogen; relative thermal stability of the hydrogen "
            "halides explained via bond strength. Relative reactivity of halide ions "
            "as reducing agents; their reactions with aqueous silver ions followed by "
            "aqueous ammonia, and with concentrated sulfuric acid (balanced "
            "equations). The disproportionation of chlorine with cold and with hot "
            "aqueous sodium hydroxide, tracked via oxidation-number change; the use "
            "of chlorine in water purification via the bactericidal species HOCl and "
            "ClO-."
        ),
        subsections=(
            "11.1 Physical properties of the Group 17 elements",
            "11.2 The chemical properties of the halogen elements and the hydrogen halides",
            "11.3 Some reactions of the halide ions",
            "11.4 The reactions of chlorine",
        ),
    ),
    Topic(
        code="ch12",
        number=12,
        name="Nitrogen and sulfur",
        blurb=(
            "The lack of reactivity of nitrogen, explained by its triple bond "
            "strength and lack of polarity. The basicity of ammonia via the "
            "Bronsted-Lowry theory, the structure and acid-base formation of the "
            "ammonium ion, and displacement of ammonia from ammonium salts by an "
            "acid-base reaction. Natural and man-made sources of oxides of nitrogen "
            "and their catalytic removal from vehicle exhaust gases; NO and NO2 "
            "reacting with unburned hydrocarbons to form peroxyacetyl nitrate (PAN), "
            "a component of photochemical smog; the role of NO and NO2 in acid rain, "
            "both directly and by catalysing the oxidation of atmospheric sulfur "
            "dioxide."
        ),
        subsections=("12.1 Nitrogen and sulfur",),
    ),
    Topic(
        code="ch13",
        number=13,
        name="An introduction to AS Level organic chemistry",
        blurb=(
            "Hydrocarbons (C and H only) versus alkanes (no functional group) versus "
            "the functional-group homologous series (alkene, halogenoalkane, "
            "alcohol, aldehyde, ketone, carboxylic acid, ester, amine, nitrile) whose "
            "functional group dictates physical/chemical behaviour; interpreting "
            "general, structural, displayed and skeletal formulas; systematic "
            "nomenclature of simple aliphatic molecules up to six carbons (six-plus-"
            "six for esters, straight chains only for esters and nitriles); deducing "
            "a molecular/empirical formula from any of these formula types. "
            "Terminology: homologous series; saturated/unsaturated; homolytic/"
            "heterolytic fission; free radical, initiation, propagation, "
            "termination; nucleophile/electrophile; addition, substitution, "
            "elimination, hydrolysis, condensation; oxidation ([O]) and reduction "
            "([H]) in organic redox equations. Mechanism types -- free-radical "
            "substitution, electrophilic addition, nucleophilic substitution, "
            "nucleophilic addition -- with curly arrows starting at a bond or a lone "
            "pair. Straight-chain, branched and cyclic molecules; the shape and bond "
            "angles at sp, sp2 and sp3 hybridised atoms, their sigma/pi bond "
            "arrangement, and the term planar (e.g. ethene). Structural isomerism "
            "(chain, positional, functional group) and stereoisomerism (geometrical "
            "cis/trans in alkenes, from restricted rotation about a pi bond; optical, "
            "from a chiral centre giving two enantiomers); identifying chiral centres "
            "and cis/trans isomerism in a given structural formula, including cyclic "
            "compounds, and deducing the possible isomers of a molecular formula. "
            "(The reactions of a specific functional group belong to that group's own "
            "topic -- Hydrocarbons, Halogen compounds, and so on -- not here.)"
        ),
        subsections=(
            "13.1 Formulas, functional groups and the naming of organic compounds",
            "13.2 Characteristic organic reactions",
            "13.3 Shapes of organic molecules; sigma and pi bonds",
            "13.4 Isomerism: structural isomerism and stereoisomerism",
        ),
    ),
    Topic(
        code="ch14",
        number=14,
        name="Hydrocarbons",
        blurb=(
            "Alkanes: preparation by hydrogenating an alkene (H2, Pt/Ni, heat) or "
            "cracking a longer alkane (heat, Al2O3); complete and incomplete "
            "combustion; free-radical substitution by Cl2 or Br2 in UV light "
            "(ethane example) via initiation/propagation/termination; cracking to "
            "obtain more useful, lower-Mr alkanes and alkenes from crude oil "
            "fractions; general unreactivity toward polar reagents from strong, "
            "non-polar C-H bonds; environmental consequences and catalytic removal "
            "of CO, NOx and unburnt hydrocarbons from combustion. Alkenes: "
            "preparation by elimination of HX from a halogenoalkane (ethanolic NaOH, "
            "heat), dehydration of an alcohol, or cracking; electrophilic addition of "
            "hydrogen, steam, a hydrogen halide or a halogen; oxidation by cold "
            "dilute acidified KMnO4 to a diol, and by hot concentrated acidified "
            "KMnO4 to rupture the C=C bond and locate alkene position from the "
            "products; addition polymerisation (ethene, propene); aqueous bromine as "
            "a test for C=C; the electrophilic addition mechanism (bromine/ethene, "
            "hydrogen bromide/propene); the inductive effect of alkyl groups "
            "stabilising primary/secondary/tertiary cations, explaining Markovnikov "
            "addition."
        ),
        subsections=(
            "14.1 Alkanes",
            "14.2 Alkenes",
        ),
    ),
    Topic(
        code="ch15",
        number=15,
        name="Halogen compounds",
        blurb=(
            "Halogenoalkane preparation: free-radical substitution of an alkane, "
            "electrophilic addition of a halogen or hydrogen halide to an alkene, or "
            "substitution of an alcohol (HX(g); KCl + concentrated H2SO4 or H3PO4; "
            "PCl3 + heat; PCl5; or SOCl2). Classifying primary/secondary/tertiary. "
            "Nucleophilic substitution: NaOH(aq) + heat to an alcohol, KCN in "
            "ethanol + heat to a nitrile, NH3 in ethanol under pressure to an amine, "
            "and aqueous silver nitrate in ethanol to identify the halogen present "
            "(bromoethane example). Elimination with ethanolic NaOH + heat to an "
            "alkene (bromoethane example). The SN1 and SN2 mechanisms, the inductive "
            "effect of alkyl groups, and primary halogenoalkanes favouring SN2, "
            "tertiary favouring SN1, secondary a mixture; differing reactivity of "
            "halogenoalkanes explained by relative C-X bond strength, as shown by "
            "rate of reaction with aqueous silver nitrate."
        ),
        subsections=("15.1 Halogenoalkanes",),
    ),
    Topic(
        code="ch16",
        number=16,
        name="Hydroxy compounds",
        blurb=(
            "Alcohol preparation: electrophilic addition of steam to an alkene; cold "
            "dilute acidified KMnO4 on an alkene to a diol; substitution of a "
            "halogenoalkane with NaOH(aq) + heat; reduction of an aldehyde/ketone "
            "with NaBH4 or LiAlH4; reduction of a carboxylic acid with LiAlH4; "
            "hydrolysis of an ester. Reactions: combustion; substitution to a "
            "halogenoalkane (same reagent set as halogenoalkane preparation); "
            "reaction with Na(s); oxidation with acidified K2Cr2O7 or KMnO4 -- "
            "primary alcohols to aldehydes (by distillation), then on to carboxylic "
            "acids (by refluxing); secondary alcohols to ketones; tertiary alcohols "
            "resist oxidation; dehydration to an alkene (heated catalyst or "
            "concentrated acid); esterification with a carboxylic acid and "
            "concentrated H2SO4 catalyst (ethanol example). Classifying primary/"
            "secondary/tertiary alcohols, including those with more than one -OH "
            "group; the orange-to-green colour change of acidified K2Cr2O7 as a "
            "distinguishing test. Deducing a CH3CH(OH)- group from a positive "
            "iodoform reaction (alkaline I2(aq), yellow triiodomethane precipitate, "
            "plus RCO2-). The acidity of alcohols compared with water."
        ),
        subsections=("16.1 Alcohols",),
    ),
    Topic(
        code="ch17",
        number=17,
        name="Carbonyl compounds",
        blurb=(
            "Preparation of aldehydes (from primary alcohols) and ketones (from "
            "secondary alcohols) by oxidation with acidified K2Cr2O7 or KMnO4 and "
            "distillation. Reduction with NaBH4 or LiAlH4 back to alcohols. "
            "Nucleophilic addition of HCN (KCN catalyst, heat) to hydroxynitriles "
            "(ethanal and propanone examples) and its mechanism. Using "
            "2,4-dinitrophenylhydrazine (2,4-DNPH) to detect a carbonyl group; "
            "distinguishing an aldehyde from a ketone via Fehling's or Tollens' "
            "reagent, or ease of oxidation. Deducing a CH3CO- group from a positive "
            "iodoform reaction (alkaline I2(aq), yellow triiodomethane precipitate, "
            "plus RCO2-)."
        ),
        subsections=("17.1 Aldehydes and ketones",),
    ),
    Topic(
        code="ch18",
        number=18,
        name="Carboxylic acids and derivatives",
        blurb=(
            "Carboxylic acid preparation: oxidation of a primary alcohol or "
            "aldehyde (acidified K2Cr2O7 or KMnO4, refluxing); hydrolysis of a "
            "nitrile or an ester with dilute acid or alkali, then acidification. "
            "Reactions: with reactive metals to a salt + H2; neutralisation with "
            "alkalis; with carbonates to a salt + H2O + CO2; esterification with an "
            "alcohol (concentrated H2SO4 catalyst); reduction by LiAlH4 to a primary "
            "alcohol. Esters: formed by condensation of an alcohol and a carboxylic "
            "acid (concentrated H2SO4 catalyst); hydrolysed by dilute acid or dilute "
            "alkali plus heat."
        ),
        subsections=(
            "18.1 Carboxylic acids",
            "18.2 Esters",
        ),
    ),
    Topic(
        code="ch19",
        number=19,
        name="Nitrogen compounds",
        blurb=(
            "Primary amine preparation from a halogenoalkane + NH3 in ethanol "
            "heated under pressure (amine classification is not tested at AS). "
            "Nitrile preparation from a halogenoalkane + KCN in ethanol + heat; "
            "hydroxynitrile preparation from an aldehyde/ketone + HCN (KCN "
            "catalyst). Hydrolysis of a nitrile with dilute acid or dilute alkali, "
            "followed by acidification, to a carboxylic acid."
        ),
        subsections=(
            "19.1 Primary amines",
            "19.2 Nitriles and hydroxynitriles",
        ),
    ),
    Topic(
        code="ch20",
        number=20,
        name="Polymerisation",
        blurb=(
            "Addition polymerisation exemplified by poly(ethene) and "
            "poly(chloroethene) (PVC); deducing an addition polymer's repeat unit "
            "from a given monomer, and identifying the monomer(s) present in a given "
            "section of a polymer molecule; the difficulty of disposing of "
            "poly(alkene)s -- non-biodegradability and harmful combustion products."
        ),
        subsections=("20.1 Addition polymerisation",),
    ),
    Topic(
        code="ch21",
        number=21,
        name="Organic synthesis",
        blurb=(
            "For a molecule with several functional groups: identifying them from "
            "the syllabus reactions and predicting the molecule's properties and "
            "reactions. Devising a multi-step synthetic route to prepare an organic "
            "molecule using syllabus reactions; analysing a given synthetic route in "
            "terms of the reaction type and reagents used at each step, and any "
            "possible by-products. (The individual reactions used along such a route "
            "belong to their own functional-group topics; this is the topic that "
            "stitches them into a route.)"
        ),
        subsections=("21.1 Organic synthesis",),
    ),
    Topic(
        code="ch22",
        number=22,
        name="Analytical techniques",
        blurb=(
            "Analysing an infrared spectrum of a simple molecule to identify "
            "functional groups from characteristic absorption ranges. Analysing mass "
            "spectra in terms of m/e values and isotopic abundance; calculating an "
            "element's relative atomic mass from isotopic abundances or a mass "
            "spectrum; deducing an organic molecule's molecular mass from the "
            "molecular ion (M+) peak; suggesting the identity of fragment ions from "
            "simple fragmentation. Deducing the number of carbon atoms in a compound "
            "from the [M+1]+ peak (using its ~1.1% natural 13C abundance); deducing "
            "the presence of a bromine or chlorine atom from the [M+2]+ peak."
        ),
        subsections=(
            "22.1 Infrared spectroscopy",
            "22.2 Mass spectrometry",
        ),
    ),
)


PHYSICS = Taxonomy(
    key="9702",
    subject_code="9702",
    papers=(1, 2),
    subject_name="Physics",
    topics=_PHYSICS_TOPICS,
)
FURTHER_PURE_1 = Taxonomy(
    key="9231p1",
    subject_code="9231",
    papers=(1,),
    subject_name="Further Pure Mathematics",
    topics=_FURTHER_PURE_1_TOPICS,
)
FURTHER_PROB_STATS = Taxonomy(
    key="9231p4",
    subject_code="9231",
    papers=(4,),
    subject_name="Further Probability & Statistics",
    topics=_FURTHER_PROB_STATS_TOPICS,
)
PURE_MATH_1 = Taxonomy(
    key="9709p1",
    subject_code="9709",
    papers=(1,),
    subject_name="Pure Mathematics 1",
    topics=_PURE_MATH_1_TOPICS,
)
PROB_STATS_1 = Taxonomy(
    key="9709p5",
    subject_code="9709",
    papers=(5,),
    subject_name="Probability & Statistics 1",
    topics=_PROB_STATS_1_TOPICS,
)
# Bare code as `key`, like PHYSICS -- one taxonomy spans both papers, since P1
# (MCQ) and P2 (structured) both examine the same full AS syllabus content.
CHEMISTRY = Taxonomy(
    key="9701",
    subject_code="9701",
    papers=(1, 2),
    subject_name="Chemistry",
    topics=_CHEMISTRY_TOPICS,
)

TAXONOMIES: tuple[Taxonomy, ...] = (
    PHYSICS,
    FURTHER_PURE_1,
    FURTHER_PROB_STATS,
    PURE_MATH_1,
    PROB_STATS_1,
    CHEMISTRY,
)

# Backwards-compat: several modules still ``from paper_finder.topics import TOPICS``
# meaning the Physics list. Kept as an alias; new code should go through a Taxonomy.
TOPICS: tuple[Topic, ...] = PHYSICS.topics

ALL_TOPICS: tuple[Topic, ...] = tuple(t for tax in TAXONOMIES for t in tax.topics)
BY_CODE: dict[str, Topic] = {t.code: t for t in ALL_TOPICS}
CODES: frozenset[str] = frozenset(BY_CODE)


def taxonomy_for(subject_code: str, paper: int | None) -> Taxonomy | None:
    """The taxonomy for a paper, from its CIE subject code and paper number.

    ``paper`` may be ``None`` (a paper-less filename such as grade thresholds); it
    then matches on subject code alone and returns the first taxonomy for it.
    """
    for tax in TAXONOMIES:
        if tax.subject_code != subject_code:
            continue
        if paper is None or paper in tax.papers:
            return tax
    return None


def taxonomy_by_name(subject_name: str) -> Taxonomy | None:
    """The taxonomy whose ``subject_name`` matches (i.e. the UI Subject value)."""
    for tax in TAXONOMIES:
        if tax.subject_name == subject_name:
            return tax
    return None
