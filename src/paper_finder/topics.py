"""CIE syllabus taxonomies -- one per (subject, paper group) the corpus covers.

Single source of truth for topic codes, display names, and the blurbs the
classifier prompt is built from. Multi-label: a question may belong to several
sections (a "define force, then check homogeneity" question is both s01 and s03).

Five taxonomies today:

* ``PHYSICS`` -- 9702 Papers 1 & 2, sections ``s01``..``s11``, from "Cambridge
  International AS & A Level Physics 9702 syllabus for 2025, 2026 and 2027".
* ``FURTHER_PURE_1`` -- 9231 Paper 1 (Further Pure Mathematics 1), ``fp1``..``fp7``.
* ``FURTHER_PROB_STATS`` -- 9231 Paper 4 (Further Probability & Statistics),
  ``fs1``..``fs5``.
* ``PURE_MATH_1`` -- 9709 Paper 1 (Pure Mathematics 1), ``pm1``..``pm8``.
* ``PROB_STATS_1`` -- 9709 Paper 5 (Probability & Statistics 1), ``ps1``..``ps5``.

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

TAXONOMIES: tuple[Taxonomy, ...] = (
    PHYSICS,
    FURTHER_PURE_1,
    FURTHER_PROB_STATS,
    PURE_MATH_1,
    PROB_STATS_1,
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
