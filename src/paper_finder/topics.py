"""CIE syllabus taxonomies -- one per (subject, paper group) the corpus covers.

Single source of truth for topic codes, display names, and the blurbs the
classifier prompt is built from. Multi-label: a question may belong to several
sections (a "define force, then check homogeneity" question is both s01 and s03).

Fourteen taxonomies today:

* ``PHYSICS`` -- 9702 Papers 1 & 2, sections ``s01``..``s11``, from "Cambridge
  International AS & A Level Physics 9702 syllabus for 2025, 2026 and 2027".
* ``FURTHER_PURE_1`` -- 9231 Paper 1 (Further Pure Mathematics 1), ``fp1``..``fp7``.
* ``FURTHER_PROB_STATS`` -- 9231 Paper 4 (Further Probability & Statistics),
  ``fs1``..``fs5``.
* ``FURTHER_PURE_2`` -- 9231 Paper 2 (Further Pure Mathematics 2),
  ``fp21``..``fp26``, from "Cambridge International AS & A Level Further
  Mathematics 9231 syllabus for 2028, 2029 and 2030" (pp.20-23). Builds on
  ``FURTHER_PURE_1``. An A Level paper, not AS Level like ``FURTHER_PURE_1``/
  ``FURTHER_PROB_STATS`` above it; its own single-paper subject, same
  disjoint-content shape as those two -- ``fp2x`` extends the ``fp`` family
  the same way ``pm3x`` extends ``pm`` below, without colliding with ``fp1``..
  ``fp7`` as strings.
* ``FURTHER_MECHANICS`` -- 9231 Paper 3 (Further Mechanics), ``fm1``..``fm6``,
  same syllabus (pp.24-26). Builds on 9709 Paper 4 (``MECHANICS``). A Level.
  A new content family within 9231, so it takes the unclaimed ``fm`` prefix
  rather than extending an existing one.
* ``PURE_MATH_1`` -- 9709 Paper 1 (Pure Mathematics 1), ``pm1``..``pm8``.
* ``PROB_STATS_1`` -- 9709 Paper 5 (Probability & Statistics 1), ``ps1``..``ps5``.
* ``PURE_MATH_3`` -- 9709 Paper 3 (Pure Mathematics 3), ``pm31``..``pm39``, from
  "Cambridge International AS & A Level Mathematics 9709 syllabus for 2028,
  2029 and 2030" (pp.26-30). Builds on ``PURE_MATH_1``; an A Level paper, not
  AS Level like every taxonomy above it.
* ``MECHANICS`` -- 9709 Paper 4 (Mechanics), ``mc1``..``mc5``, same syllabus
  (pp.31-33). A Level.
* ``PROB_STATS_2`` -- 9709 Paper 6 (Probability & Statistics 2),
  ``ps21``..``ps25``, same syllabus (pp.37-39). Builds on ``PROB_STATS_1`` and
  ``PURE_MATH_3``. A Level. ``PURE_MATH_3``/``MECHANICS``/``PROB_STATS_2`` are
  each their own single-paper subject, same disjoint-content shape as
  ``PURE_MATH_1``/``PROB_STATS_1`` -- not one taxonomy spanning several papers.
* ``CHEMISTRY`` -- 9701 Papers 1 & 2, sections ``ch01``..``ch22``, from
  "Cambridge International AS & A Level Chemistry 9701 syllabus for 2025, 2026
  and 2027" (AS Level subject content, pp.16-38). Like ``PHYSICS``, one
  taxonomy spans both papers -- P1 (MCQ) and P2 (structured) both examine the
  same full AS syllabus, unlike 9231/9709's disjoint-content paper splits.
* ``BIOLOGY`` -- 9700 Papers 1 & 2, sections ``bi01``..``bi11``, from
  "Cambridge International AS & A Level Biology 9700 syllabus for 2028, 2029
  and 2030" (AS Level subject content, pp.16-32). Same shape as ``CHEMISTRY``
  -- one taxonomy spans both papers.
* ``ECONOMICS`` -- 9708 Papers 1 & 2, sections ``ec01``..``ec06``, from
  "Cambridge International AS & A Level Economics 9708 syllabus for 2026, 2027
  and 2028" (AS Level content, pp.15-23). Same shape as ``CHEMISTRY``/
  ``BIOLOGY`` -- one taxonomy spans both papers, just a coarser 6-section
  split since that is the syllabus's own top-level section count here.
* ``COMPUTER_SCIENCE`` -- 9618 Papers 1 & 2, sections ``cs01``..``cs12``, from
  "Cambridge International AS & A Level Computer Science 9618 syllabus for
  2027, 2028 and 2029" (AS content, pp.14-31). One taxonomy spans both papers
  like ``PHYSICS``, but the syllabus splits content by paper: Paper 1 examines
  sections 1-8 only and Paper 2 sections 9-12 only, recorded per topic in
  ``Topic.papers`` (and enforced by ``labels.parse_labels``). Both papers are
  structured.

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
    # Papers (of its taxonomy) that examine this section; empty = all of them.
    # Set only where the syllabus splits content by paper (Computer Science).
    papers: tuple[int, ...] = ()


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

# --- 9231 Paper 2: Further Pure Mathematics 2 (syllabus section 2) ------------
# Builds on Paper 1 (FURTHER_PURE_1). An A Level paper -- see PURE_MATH_3 for
# the same disjoint-content, single-paper-subject shape.

_FURTHER_PURE_2_TOPICS: tuple[Topic, ...] = (
    Topic(
        code="fp21",
        number=1,
        name="Hyperbolic functions",
        blurb=(
            "Understanding the definitions of the hyperbolic functions sinh x, cosh x, "
            "tanh x, sech x, cosech x, coth x in terms of the exponential function, and "
            "sketching their graphs. Proving and using identities involving hyperbolic "
            "functions, e.g. cosh^2 x - sinh^2 x = 1, sinh 2x = 2 sinh x cosh x, and "
            "similar results corresponding to standard trigonometric identities. "
            "Understanding and using the definitions of the inverse hyperbolic functions "
            "and deriving and using their logarithmic forms."
        ),
        subsections=("2.1 Hyperbolic functions",),
    ),
    Topic(
        code="fp22",
        number=2,
        name="Matrices",
        blurb=(
            "Formulating a problem involving the solution of 3 linear simultaneous "
            "equations in 3 unknowns as a matrix equation, or vice versa, understanding "
            "the cases of consistency or inconsistency, relating them to the singularity "
            "or otherwise of the corresponding matrix, solving consistent systems and "
            "interpreting geometrically (e.g. three planes meeting in a common point or "
            "line, or having no common points). Understanding the terms 'characteristic "
            "equation', 'eigenvalue' and 'eigenvector' for square matrices, including use "
            "of Ae = lambda e to prove simple properties. Finding eigenvalues and "
            "eigenvectors of 2x2 and 3x3 matrices (real and distinct only). Expressing a "
            "square matrix as QDQ^-1, where D is diagonal and Q's columns are "
            "eigenvectors, and using this e.g. to find powers of a matrix. Using the fact "
            "that a square matrix satisfies its own characteristic equation, e.g. in "
            "finding successive powers of a matrix or an inverse matrix (2x2 or 3x3 only)."
        ),
        subsections=("2.2 Matrices",),
    ),
    Topic(
        code="fp23",
        number=3,
        name="Differentiation",
        blurb=(
            "Differentiating hyperbolic functions and sin^-1 x, cos^-1 x, sinh^-1 x, "
            "cosh^-1 x and tanh^-1 x. Obtaining an expression for d^2y/dx^2 where the "
            "relation between x and y is defined implicitly or parametrically, including "
            "successive implicit differentiation steps. Deriving and using the first few "
            "terms of a Maclaurin's series for a function (derivation of a general term "
            "is not included)."
        ),
        subsections=("2.3 Differentiation",),
    ),
    Topic(
        code="fp24",
        number=4,
        name="Integration",
        blurb=(
            "Integrating hyperbolic functions and recognising integrals of the forms "
            "1/sqrt(a^2 - x^2), 1/(a^2 + x^2) and 1/sqrt(a^2 + x^2), integrating "
            "associated functions using trigonometric or hyperbolic substitutions "
            "(including completing the square where necessary). Deriving and using "
            "reduction formulae for the evaluation of definite integrals. Understanding "
            "how the area under a curve may be approximated by areas of rectangles, and "
            "using rectangles to estimate or set bounds for the area under a curve or to "
            "derive inequalities or limits concerning sums. Using integration to find arc "
            "lengths (Cartesian, including a parameter, or polar coordinates) and surface "
            "areas of revolution about an axis for curves in Cartesian coordinates, "
            "including the use of a parameter (polar surface areas are not required)."
        ),
        subsections=("2.4 Integration",),
    ),
    Topic(
        code="fp25",
        number=5,
        name="Complex numbers",
        blurb=(
            "Understanding de Moivre's theorem for a positive or negative integer "
            "exponent in terms of the geometrical effect of multiplication and division "
            "of complex numbers, and proving it for a positive integer exponent (e.g. by "
            "induction). Using de Moivre's theorem for a positive or negative rational "
            "exponent to express trigonometric ratios of multiple angles in terms of "
            "powers of trigonometric ratios of the fundamental angle, to express powers "
            "of sin theta and cos theta in terms of multiple angles, in the summation of "
            "series, and in finding and using the nth roots of unity."
        ),
        subsections=("2.5 Complex numbers",),
    ),
    Topic(
        code="fp26",
        number=6,
        name="Differential equations",
        blurb=(
            "Finding an integrating factor for a first order linear differential equation "
            "and using it to find the general solution. Recalling the meaning of "
            "'complementary function' and 'particular integral' and that the general "
            "solution is their sum. Finding the complementary function for a first or "
            "second order linear differential equation with constant coefficients, "
            "including auxiliary equations with distinct real roots, a repeated real "
            "root, or conjugate complex roots. Recalling the form of, and finding, a "
            "particular integral where a polynomial, a e^(bx) or a cos px + b sin px is a "
            "suitable form. Using a given substitution to reduce a differential equation "
            "to first or second order linear with constant coefficients, or to a first "
            "order equation with separable variables. Using initial conditions to find a "
            "particular solution and interpreting a solution in terms of a modelled "
            "problem."
        ),
        subsections=("2.6 Differential equations",),
    ),
)

# --- 9231 Paper 3: Further Mechanics (syllabus section 3) ---------------------
# Builds on 9709 Paper 4 (MECHANICS). A new content family within 9231, so it
# takes the unclaimed "fm" prefix rather than extending an existing one.

_FURTHER_MECHANICS_TOPICS: tuple[Topic, ...] = (
    Topic(
        code="fm1",
        number=1,
        name="Motion of a projectile",
        blurb=(
            "Modelling the motion of a projectile as a particle moving with constant "
            "acceleration and understanding limitations of the model (vector methods are "
            "not required). Using horizontal and vertical equations of motion to solve "
            "problems on the motion of projectiles, including finding the magnitude and "
            "direction of the velocity at a given time or position, the range on a "
            "horizontal plane and the greatest height reached. Deriving and using the "
            "Cartesian equation of the trajectory of a projectile, including problems "
            "where the initial speed and/or angle of projection may be unknown."
        ),
        subsections=("3.1 Motion of a projectile",),
    ),
    Topic(
        code="fm2",
        number=2,
        name="Equilibrium of a rigid body",
        blurb=(
            "Calculating the moment of a force about a point (coplanar forces only). "
            "Using the result that the effect of gravity on a rigid body is equivalent to "
            "a single force acting at the centre of mass, and identifying the centre of "
            "mass of a uniform body by symmetry, or from given information for a "
            "triangular lamina or other simple shape. Determining the position of the "
            "centre of mass of a composite body by considering an equivalent system of "
            "particles (simple cases, e.g. a uniform L-shaped lamina, or a uniform cone "
            "joined to a uniform hemisphere of the same radius). Using the principle that "
            "a rigid body in equilibrium under coplanar forces has zero vector sum of "
            "forces and zero sum of moments about any point (and the converse), and "
            "solving equilibrium problems for a single rigid body under coplanar forces, "
            "including those involving toppling or sliding."
        ),
        subsections=("3.2 Equilibrium of a rigid body",),
    ),
    Topic(
        code="fm3",
        number=3,
        name="Circular motion",
        blurb=(
            "Understanding the concept of angular speed for a particle moving in a "
            "circle and using v = r*omega. Understanding that the acceleration of a "
            "particle moving in a circle with constant speed is directed towards the "
            "centre, and using the formulae r*omega^2 and v^2/r (proof not required). "
            "Solving problems modelled by a particle moving in a horizontal circle with "
            "constant speed, and problems modelled by a particle moving in a vertical "
            "circle without loss of energy, including finding a normal contact force or "
            "the tension in a string, locating points where these are zero, and "
            "conditions for complete circular motion."
        ),
        subsections=("3.3 Circular motion",),
    ),
    Topic(
        code="fm4",
        number=4,
        name="Hooke's law",
        blurb=(
            "Using Hooke's law as a model relating the force in an elastic string or "
            "spring to the extension or compression, and understanding the term modulus "
            "of elasticity. Using the formula for the elastic potential energy stored in "
            "a string or spring (proof not required). Solving problems involving forces "
            "due to elastic strings or springs, including those where considerations of "
            "work and energy are needed, e.g. a particle moving horizontally, vertically "
            "or on an inclined plane while attached to one or more strings or springs, or "
            "attached to an elastic string acting as a 'conical pendulum'."
        ),
        subsections=("3.4 Hooke's law",),
    ),
    Topic(
        code="fm5",
        number=5,
        name="Linear motion under a variable force",
        blurb=(
            "Solving problems which can be modelled as the linear motion of a particle "
            "under the action of a variable force, by setting up and solving an "
            "appropriate differential equation, including use of v dv/dx for "
            "acceleration where appropriate. Calculus required is restricted to content "
            "from Pure Mathematics 3; only differential equations in which the variables "
            "are separable are included."
        ),
        subsections=("3.5 Linear motion under a variable force",),
    ),
    Topic(
        code="fm6",
        number=6,
        name="Momentum",
        blurb=(
            "Recalling Newton's experimental law and the definition of the coefficient "
            "of restitution e (0 <= e <= 1), and the meaning of 'perfectly elastic' "
            "(e = 1) and 'inelastic' (e = 0). Using conservation of linear momentum "
            "and/or Newton's experimental law to solve problems modelled as the direct or "
            "oblique impact of two smooth spheres, or the direct or oblique impact of a "
            "smooth sphere with a fixed surface."
        ),
        subsections=("3.6 Momentum",),
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


# --- 9709 Paper 3: Pure Mathematics 3 (syllabus section 3, A Level) -----------
# "Knowledge of the content of Paper 1: Pure Mathematics 1 is assumed" -- the
# syllabus explicitly builds on PURE_MATH_1 rather than repeating it.

_PURE_MATH_3_TOPICS: tuple[Topic, ...] = (
    Topic(
        code="pm31",
        number=1,
        name="Algebra",
        blurb=(
            "Understanding the meaning of |x|, sketching y = |ax + b|, and using "
            "relations such as |a| = |b| iff a^2 = b^2 and |x - a| < b iff "
            "a - b < x < a + b when solving equations and inequalities, "
            "e.g. |3x - 2| = |2x + 7|, 2x + 5 < |x + 1|. Dividing a polynomial of "
            "degree not exceeding 4 by a linear or quadratic polynomial and "
            "identifying the quotient and remainder (which may be zero). Using the "
            "factor theorem and the remainder theorem, including factors of the form "
            "(ax + b) where the coefficient of x is not unity. Expressing a rational "
            "function in partial fractions where the denominator is no more "
            "complicated than (ax + b)(cx + d)(ex + f), (ax + b)(cx + d)^2 or "
            "(ax + b)(cx^2 + d), excluding cases where the numerator's degree "
            "exceeds the denominator's. Using the expansion of (1 + x)^n for "
            "rational n and |x| < 1, including adapting the standard series to "
            "expand e.g. 1/sqrt(1 - 2x)."
        ),
        subsections=("3.1 Algebra",),
    ),
    Topic(
        code="pm32",
        number=2,
        name="Logarithmic and exponential functions",
        blurb=(
            "Understanding the relationship between logarithms and indices and "
            "using the laws of logarithms (excluding change of base). Understanding "
            "the definition and properties of e^x and ln x, including their "
            "relationship as inverse functions, their graphs, and the graph of "
            "y = e^(kx) for both positive and negative k. Using logarithms to solve "
            "equations and inequalities where the unknown appears in indices, "
            "e.g. 2^x < 5, 3^(2x - 1) > 4^(1 - x). Using logarithms to transform a "
            "given relationship to linear form and hence determine unknown "
            "constants from the gradient and/or intercept: y = kx^n gives "
            "ln y = ln k + n ln x, which is linear in ln x and ln y; y = k(a^x) "
            "gives ln y = ln k + x ln a, which is linear in x and ln y."
        ),
        subsections=("3.2 Logarithmic and exponential functions",),
    ),
    Topic(
        code="pm33",
        number=3,
        name="Trigonometry",
        blurb=(
            "Understanding the relationship of secant, cosecant and cotangent to "
            "cosine, sine and tangent, and using properties and graphs of all six "
            "trig functions for angles of any magnitude. Using trig identities for "
            "simplification and exact evaluation of expressions and in solving "
            "equations, including sec^2(theta) = 1 + tan^2(theta), "
            "cosec^2(theta) = 1 + cot^2(theta), the expansions of "
            "sin(A +/- B), cos(A +/- B) and tan(A +/- B), the double-angle formulae "
            "for sin 2A, cos 2A and tan 2A, and expressing a cos(theta) + b sin(theta) "
            "in the forms R sin(theta +/- alpha) and R cos(theta +/- alpha), "
            "e.g. simplifying cos(x - 30deg) - sqrt(3) sin(x - 60deg), or solving "
            "tan(theta) + cot(theta) = 4."
        ),
        subsections=("3.3 Trigonometry",),
    ),
    Topic(
        code="pm34",
        number=4,
        name="Differentiation",
        blurb=(
            "Using the derivatives of e^x, ln x, sin x, cos x, tan x and "
            "tan^-1(x), together with constant multiples, sums, differences and "
            "composites (derivatives of sin^-1(x) and cos^-1(x) are not required). "
            "Differentiating products and quotients, e.g. (2x - 3)/sqrt(4x + 2), "
            "x^2 ln x, x e^(1 - x^2). Finding and using the first derivative of a "
            "function defined parametrically (e.g. x = t - e^(2t), y = t + e^(2t)) "
            "or implicitly (e.g. x^2 + y^2 = xy + 7), including problems involving "
            "tangents and normals."
        ),
        subsections=("3.4 Differentiation",),
    ),
    Topic(
        code="pm35",
        number=5,
        name="Integration",
        blurb=(
            "Extending 'reverse differentiation' to integrate e^(ax+b), "
            "1/(ax + b), sin(ax + b), cos(ax + b), sec^2(ax + b) and "
            "1/(a^2 + x^2), including examples such as 3/(1 + 2x^2). Using trig "
            "relationships (e.g. double-angle formulae) in carrying out "
            "integration, such as sin^2(x) or cos^2(2x). Integrating rational "
            "functions by decomposition into partial fractions (restricted to the "
            "types specified in Algebra/3.1 above). Recognising an integrand of the "
            "form f'(x)/f(x) and integrating such functions, e.g. x/(1 + x^2), "
            "tan x. Recognising when an integrand can usefully be regarded as a "
            "product and using integration by parts, e.g. x sin 2x, x^2 e^-x, ln x, "
            "x tan^-1(x). Using a given substitution to simplify and evaluate a "
            "definite or indefinite integral, e.g. integrating sin^2(2x) cos(x) "
            "using u = sin x."
        ),
        subsections=("3.5 Integration",),
    ),
    Topic(
        code="pm36",
        number=6,
        name="Numerical solution of equations",
        blurb=(
            "Locating approximately a root of an equation by graphical "
            "considerations and/or searching for a sign change, e.g. finding a "
            "pair of consecutive integers between which a root lies. Understanding "
            "the idea of, and the notation for, a sequence of approximations "
            "converging to a root of an equation. Understanding how a given simple "
            "iterative formula x_(n+1) = F(x_n) relates to the equation being "
            "solved, and using a given iteration, or one based on a given "
            "rearrangement, to determine a root to a prescribed degree of accuracy "
            "(knowledge of the convergence condition is not included, but "
            "understanding that an iteration may fail to converge is expected)."
        ),
        subsections=("3.6 Numerical solution of equations",),
    ),
    Topic(
        code="pm37",
        number=7,
        name="Vectors",
        blurb=(
            "Using standard vector notations, including column vectors, "
            "xi + yj + zk, AB (displacement vector) and a. Carrying out addition "
            "and subtraction of vectors and multiplication of a vector by a "
            "scalar, and interpreting these geometrically, e.g. 'OABC is a "
            "parallelogram' is equivalent to OB = OA + OC. Calculating the "
            "magnitude of a vector and using unit vectors, displacement vectors "
            "and position vectors in 2 or 3 dimensions. Understanding the "
            "significance of the symbols in r = a + tb and finding the equation of "
            "a line given sufficient information. Determining whether two lines "
            "are parallel, intersect or are skew, and finding the point of "
            "intersection when it exists (the shortest distance between skew "
            "lines and the common perpendicular are not required). Using formulae "
            "to calculate the scalar product of two vectors and using scalar "
            "products in problems involving lines and points, e.g. the angle "
            "between two lines, or the foot of the perpendicular from a point to "
            "a line, including 3D objects such as cuboids and tetrahedra "
            "(the vector product is not required)."
        ),
        subsections=("3.7 Vectors",),
    ),
    Topic(
        code="pm38",
        number=8,
        name="Differential equations",
        blurb=(
            "Formulating a simple statement involving a rate of change as a "
            "differential equation, including introducing and evaluating a "
            "constant of proportionality where necessary. Finding by integration "
            "a general form of solution for a first order differential equation "
            "in which the variables are separable (including any of the "
            "integration techniques from Integration/3.5 above). Using an initial "
            "condition to find a particular solution. Interpreting the solution "
            "of a differential equation in the context of a problem being "
            "modelled by the equation, where no specialised knowledge of the "
            "context is required."
        ),
        subsections=("3.8 Differential equations",),
    ),
    Topic(
        code="pm39",
        number=9,
        name="Complex numbers",
        blurb=(
            "Understanding the idea of a complex number, the terms real part, "
            "imaginary part, modulus, argument and conjugate (notations Re z, "
            "Im z, |z|, arg z, z*), and that two complex numbers are equal iff "
            "both real and imaginary parts are equal. Carrying out addition, "
            "subtraction, multiplication and division of complex numbers in "
            "Cartesian form x + iy, showing full working for multiplication or "
            "division. Using the result that non-real roots of a polynomial "
            "equation with real coefficients occur in conjugate pairs, e.g. "
            "solving a cubic or quartic given one complex root. Representing "
            "complex numbers geometrically on an Argand diagram. Multiplying and "
            "dividing complex numbers in polar form r(cos theta + i sin theta) = "
            "r e^(i theta), including |z1 z2| = |z1||z2| and "
            "arg(z1 z2) = arg(z1) + arg(z2) and the corresponding division "
            "results. Finding the two square roots of a complex number, e.g. of "
            "5 + 12i in exact Cartesian form. Understanding in simple terms the "
            "geometrical effect of conjugating a complex number and of adding, "
            "subtracting, multiplying and dividing two complex numbers. "
            "Illustrating simple equations and inequalities involving complex "
            "numbers by loci in an Argand diagram, e.g. |z - a| < k, "
            "|z - a| = |z - b|, arg(z - a) = alpha."
        ),
        subsections=("3.9 Complex numbers",),
    ),
)


# --- 9709 Paper 4: Mechanics (syllabus section 4, A Level) --------------------
# Questions are mainly numerical, testing mechanical principles without heavy
# algebra or trigonometry; vector notation is not used on the question papers.
# Algebraic methods from PURE_MATH_1 are assumed.

_MECHANICS_TOPICS: tuple[Topic, ...] = (
    Topic(
        code="mc1",
        number=1,
        name="Forces and equilibrium",
        blurb=(
            "Identifying the forces acting in a given situation, e.g. by drawing "
            "a force diagram. Understanding the vector nature of force, and "
            "finding and using components and resultants (calculations are always "
            "required, not approximate scale drawings). Using the principle that, "
            "when a particle is in equilibrium, the vector sum of the forces "
            "acting is zero, equivalently that the sum of the components in any "
            "direction is zero (solutions by resolving are usually expected). "
            "Understanding that a contact force between two surfaces can be "
            "represented by a normal component and a frictional component, using "
            "the model of a 'smooth' contact and understanding its limitations. "
            "Understanding limiting friction and limiting equilibrium, recalling "
            "the coefficient of friction, and using F = mu R or F <= mu R as "
            "appropriate (terminology such as 'about to slip' means 'in limiting "
            "equilibrium'). Using Newton's third law, e.g. the force exerted by a "
            "particle on the ground is equal and opposite to the force exerted by "
            "the ground on the particle."
        ),
        subsections=("4.1 Forces and equilibrium",),
    ),
    Topic(
        code="mc2",
        number=2,
        name="Kinematics of motion in a straight line",
        blurb=(
            "Understanding distance and speed as scalar quantities and "
            "displacement, velocity and acceleration as vector quantities, "
            "restricted to motion in one dimension ('deceleration' may mean "
            "decreasing speed). Sketching and interpreting displacement-time and "
            "velocity-time graphs, appreciating that the area under a "
            "velocity-time graph represents displacement, the gradient of a "
            "displacement-time graph represents velocity, and the gradient of a "
            "velocity-time graph represents acceleration. Using differentiation "
            "and integration with respect to time to solve problems concerning "
            "displacement, velocity and acceleration (calculus restricted to "
            "Pure Mathematics 1 techniques). Using appropriate formulae for motion "
            "with constant acceleration in a straight line, including setting up more "
            "than one equation using information about different particles' "
            "motion."
        ),
        subsections=("4.2 Kinematics of motion in a straight line",),
    ),
    Topic(
        code="mc3",
        number=3,
        name="Momentum",
        blurb=(
            "Using the definition of linear momentum and showing understanding "
            "of its vector nature, for motion in one dimension only. Using "
            "conservation of linear momentum to solve problems modelled as the "
            "direct impact of two bodies, including direct impact where the "
            "bodies coalesce on impact (knowledge of impulse and the coefficient "
            "of restitution is not required)."
        ),
        subsections=("4.3 Momentum",),
    ),
    Topic(
        code="mc4",
        number=4,
        name="Newton's laws of motion",
        blurb=(
            "Applying Newton's laws of motion to the linear motion of a particle "
            "of constant mass moving under constant forces, which may include "
            "friction, tension in an inextensible string and thrust in a "
            "connecting rod (any other resisting force such as air resistance is "
            "indicated in the question). Using the relationship between mass and "
            "weight, W = mg, with g = 10 (m/s^2) unless stated otherwise. Solving "
            "problems modelled as the motion of a particle moving vertically or "
            "on an inclined plane with constant acceleration, including cases "
            "where the acceleration while moving up a rough plane differs from "
            "the acceleration moving down it. Solving problems modelled as the "
            "motion of connected particles, e.g. particles connected by a light "
            "inextensible string over a smooth pulley, or a car towing a trailer "
            "by a light rope or rigid tow-bar."
        ),
        subsections=("4.4 Newton's laws of motion",),
    ),
    Topic(
        code="mc5",
        number=5,
        name="Energy, work and power",
        blurb=(
            "Understanding the concept of work done by a force and calculating "
            "the work done by a constant force whose point of application "
            "undergoes a displacement not necessarily parallel to the force, "
            "W = Fd cos(theta) (the scalar product is not required). "
            "Understanding gravitational potential energy and kinetic energy and "
            "using the appropriate formulae. Understanding and using the "
            "relationship between the change in energy of a system and the work "
            "done by external forces, and using the principle of conservation of "
            "energy in appropriate cases, including motion that may not be linear "
            "(e.g. a child on a smooth curved slide) where only overall energy "
            "changes need considering. Using the definition of power as the rate "
            "at which a force does work, and the relationship between power, "
            "force and velocity for a force acting in the direction of motion, "
            "P = Fv, including calculating average power as work done over time "
            "taken. Solving problems involving, e.g., the instantaneous "
            "acceleration of a car moving on a hill against a resistance."
        ),
        subsections=("4.5 Energy, work and power",),
    ),
)


# --- 9709 Paper 6: Probability & Statistics 2 (syllabus section 6, A Level) ---
# "Knowledge of the content of Paper 5: Probability & Statistics 1 is assumed
# ... Knowledge of calculus within the content for Paper 3: Pure Mathematics 3
# will also be assumed."

_PROB_STATS_2_TOPICS: tuple[Topic, ...] = (
    Topic(
        code="ps21",
        number=1,
        name="The Poisson distribution",
        blurb=(
            "Using formulae to calculate probabilities for the distribution "
            "Po(m), and using the fact that if X ~ Po(m) then the mean and "
            "variance of X are each equal to m (proofs are not required). "
            "Understanding the relevance of the Poisson distribution to the "
            "distribution of random events and using it as a model. Using the "
            "Poisson distribution as an approximation to the binomial "
            "distribution where appropriate (n large and p small, approximately "
            "n > 50 and np < 5). Using the normal distribution, with continuity "
            "correction, as an approximation to the Poisson distribution where "
            "appropriate (m large, approximately m > 15)."
        ),
        subsections=("6.1 The Poisson distribution",),
    ),
    Topic(
        code="ps22",
        number=2,
        name="Linear combinations of random variables",
        blurb=(
            "Using, when solving problems, the results that E(aX + b) = "
            "aE(X) + b and Var(aX + b) = a^2 Var(X); E(aX + bY) = aE(X) + bE(Y); "
            "Var(aX + bY) = a^2 Var(X) + b^2 Var(Y) for independent X and Y; that "
            "if X has a normal distribution then so does aX + b; that if X and Y "
            "have independent normal distributions then aX + bY has a normal "
            "distribution; and that if X and Y have independent Poisson "
            "distributions then X + Y has a Poisson distribution (proofs of "
            "these results are not required)."
        ),
        subsections=("6.2 Linear combinations of random variables",),
    ),
    Topic(
        code="ps23",
        number=3,
        name="Continuous random variables",
        blurb=(
            "Understanding the concept of a continuous random variable and "
            "recalling and using properties of a probability density function "
            "defined over a single interval, where the domain may be infinite, "
            "e.g. f(x) = 4/x^3 for x >= 1. Using a probability density function "
            "to solve problems involving probabilities and to calculate the mean "
            "and variance of a distribution, including locating the median or "
            "other percentiles by direct consideration of an area using the "
            "density function (explicit knowledge of the cumulative distribution "
            "function is not included)."
        ),
        subsections=("6.3 Continuous random variables",),
    ),
    Topic(
        code="ps24",
        number=4,
        name="Sampling and estimation",
        blurb=(
            "Understanding the distinction between a sample and a population and "
            "the necessity for randomness in choosing samples, and explaining in "
            "simple terms why a given sampling method may be unsatisfactory "
            "(including an elementary understanding of random numbers in "
            "producing random samples; knowledge of particular methods such as "
            "quota or stratified sampling is not required). Recognising that a "
            "sample mean can be regarded as a random variable, using E(Xbar) = mu "
            "and Var(Xbar) = sigma^2 / n, and using the fact that Xbar has a "
            "normal distribution if X has a normal distribution. Using the "
            "Central Limit Theorem where appropriate (only an informal "
            "understanding is required: for large sample sizes the distribution "
            "of a sample mean is approximately normal). Calculating unbiased "
            "estimates of the population mean and variance from a sample, using "
            "raw or summarised data (only a simple understanding of 'unbiased' is "
            "required). Determining and interpreting a confidence interval for a "
            "population mean where the population is normally distributed with "
            "known variance or where a large sample is used, and determining an "
            "approximate confidence interval for a population proportion from a "
            "large sample."
        ),
        subsections=("6.4 Sampling and estimation",),
    ),
    Topic(
        code="ps25",
        number=5,
        name="Hypothesis tests",
        blurb=(
            "Understanding the nature of a hypothesis test, the difference "
            "between one-tailed and two-tailed tests, and the terms null "
            "hypothesis, alternative hypothesis, significance level, rejection "
            "region (critical region), acceptance region and test statistic, "
            "interpreted in the context of the question. Formulating hypotheses "
            "and carrying out a hypothesis test for a single observation from a "
            "population with a binomial or Poisson distribution, using direct "
            "evaluation of probabilities or a normal approximation to the "
            "binomial/Poisson where appropriate. Formulating hypotheses and "
            "carrying out a hypothesis test concerning the population mean where "
            "the population is normally distributed with known variance or a "
            "large sample is used. Understanding the terms Type I error and "
            "Type II error, and calculating the probabilities of making Type I "
            "and Type II errors in specific situations involving tests based on "
            "a normal distribution or direct evaluation of binomial or Poisson "
            "probabilities."
        ),
        subsections=("6.5 Hypothesis tests",),
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


# --- 9700 Papers 1 & 2: Biology (AS Level syllabus sections 1-11) --------------

_BIOLOGY_TOPICS: tuple[Topic, ...] = (
    Topic(
        code="bi01",
        number=1,
        name="Cell structure",
        blurb=(
            "Microscope skills: making temporary preparations for a light "
            "microscope; drawing cells from slides and photomicrographs; "
            "calculating magnification and actual size from drawings, "
            "photomicrographs and electron micrographs; using an eyepiece "
            "graticule and stage micrometer scale, with mm/µm/nm units; defining "
            "resolution and magnification and the difference between light and "
            "electron microscopy. Eukaryotic cell organelles and structures and "
            "their functions: cell surface membrane; nucleus, nuclear envelope and "
            "nucleolus; rough and smooth endoplasmic reticulum; Golgi body; "
            "mitochondria (including their small circular DNA); ribosomes (80S in "
            "the cytoplasm, 70S in chloroplasts and mitochondria); lysosomes; "
            "centrioles and microtubules; cilia; microvilli; chloroplasts "
            "(including their small circular DNA); cell wall; plasmodesmata; the "
            "large permanent vacuole and tonoplast of plant cells. Interpreting "
            "photomicrographs, electron micrographs and drawings of plant and "
            "animal cells; comparing plant and animal cell structure; ATP from "
            "respiration powering energy-requiring processes. The structure of a "
            "typical prokaryotic bacterium (unicellular, 1-5 µm diameter, "
            "peptidoglycan cell wall, circular DNA, 70S ribosomes, no "
            "double-membrane organelles) compared with eukaryotic plant and "
            "animal cells. Viruses as non-cellular structures with a nucleic acid "
            "core (DNA or RNA), a protein capsid and, in some, a phospholipid "
            "envelope. (The functional role each organelle plays in a specific "
            "process -- e.g. ribosomes in translation, mitochondria in "
            "respiration -- belongs to that process's own topic; this is the "
            "topic for organelle identification and structure.)"
        ),
        subsections=(
            "1.1 The microscope in cell studies",
            "1.2 Cells as the basic units of living organisms",
        ),
    ),
    Topic(
        code="bi02",
        number=2,
        name="Biological molecules",
        blurb=(
            "Testing for biological molecules: Benedict's test for reducing "
            "sugars (including a semi-quantitative version), the iodine test for "
            "starch, the emulsion test for lipids, the biuret test for proteins, "
            "and the acid-hydrolysis test for non-reducing sugars. Carbohydrates: "
            "ring forms of alpha- and beta-glucose; monomer, polymer, "
            "macromolecule, monosaccharide, disaccharide and polysaccharide; "
            "covalent bonds joining monomers into polymers; reducing sugars "
            "(glucose, fructose, maltose) versus the non-reducing sugar sucrose; "
            "glycosidic bond formation by condensation and breakage by "
            "hydrolysis; the molecular structure of starch (amylose and "
            "amylopectin), glycogen and cellulose and how each structure relates "
            "to its biological function (energy storage versus plant cell wall "
            "strength). Lipids: triglycerides as non-polar hydrophobic molecules "
            "-- fatty acids (saturated/unsaturated), glycerol, ester bonds -- and "
            "their functions; phospholipids and their hydrophilic phosphate heads "
            "and hydrophobic fatty acid tails. Proteins: amino acid structure and "
            "peptide bond formation/breakage; primary, secondary, tertiary and "
            "quaternary structure; the interactions that hold protein shape "
            "(hydrophobic interactions, hydrogen bonding, ionic bonding, covalent "
            "disulfide bonds); soluble globular proteins versus insoluble fibrous "
            "structural proteins; the quaternary structure of haemoglobin (two "
            "alpha chains, two beta chains, a haem group) and the structure of "
            "collagen and collagen fibres, each related to function. Water: "
            "hydrogen bonding between water molecules and the roles this gives "
            "water in living organisms -- solvent action, high specific heat "
            "capacity, latent heat of vaporisation."
        ),
        subsections=(
            "2.1 Testing for biological molecules",
            "2.2 Carbohydrates and lipids",
            "2.3 Proteins",
            "2.4 Water",
        ),
    ),
    Topic(
        code="bi03",
        number=3,
        name="Enzymes",
        blurb=(
            "Enzymes as globular proteins that catalyse reactions either inside "
            "cells (intracellular) or after secretion (extracellular); the mode "
            "of action of enzymes in terms of an active site, enzyme-substrate "
            "complex, lowering of activation energy and enzyme specificity, "
            "including the lock-and-key and induced-fit hypotheses. Investigating "
            "the progress of enzyme-catalysed reactions -- rate of product "
            "formation using catalase, rate of substrate disappearance using "
            "amylase -- and using a colorimeter for reactions with a colour "
            "change. Factors affecting the rate of enzyme-catalysed reactions: "
            "temperature, pH (using buffer solutions), enzyme concentration, "
            "substrate concentration and inhibitor concentration. Maximum rate of "
            "reaction (Vmax) and its use in deriving the Michaelis-Menten "
            "constant (Km) to compare different enzymes' affinity for their "
            "substrates. Reversible inhibitors -- both competitive and "
            "non-competitive -- and their effects on enzyme activity. Comparing "
            "an enzyme immobilised in alginate with the same enzyme free in "
            "solution, and the advantages of immobilised enzymes."
        ),
        subsections=(
            "3.1 Mode of action of enzymes",
            "3.2 Factors that affect enzyme action",
        ),
    ),
    Topic(
        code="bi04",
        number=4,
        name="Cell membranes and transport",
        blurb=(
            "The fluid mosaic model of membrane structure: hydrophobic and "
            "hydrophilic interactions forming the phospholipid bilayer and "
            "protein arrangement; the arrangement of cholesterol, glycolipids and "
            "glycoproteins; the roles of phospholipids, cholesterol, glycolipids, "
            "proteins and glycoproteins in membrane stability, fluidity, "
            "permeability, transport (carrier proteins and channel proteins), "
            "cell signalling (cell surface receptors) and cell recognition (cell "
            "surface antigens). The main stages of cell signalling -- secretion "
            "of a ligand, its transport to a target cell, its binding to a cell "
            "surface receptor. Movement of substances into and out of cells: "
            "simple diffusion, facilitated diffusion, osmosis, active transport, "
            "endocytosis and exocytosis; investigating diffusion and osmosis "
            "using plant tissue, dialysis (Visking) tubing and agar; the "
            "principle that surface area to volume ratio falls as size "
            "increases, and calculating SA:V for simple 3-D shapes; investigating "
            "how SA:V affects diffusion rate using agar blocks. Water potential: "
            "estimating tissue water potential from immersion experiments; "
            "explaining water movement between cells and solutions in terms of "
            "water potential, and its different effects on plant cells (turgor, "
            "plasmolysis) and animal cells (lysis, crenation). (Membrane "
            "recognition antigens are introduced here; their role in immune "
            "self/non-self recognition belongs to Immunity.)"
        ),
        subsections=(
            "4.1 Fluid mosaic membranes",
            "4.2 Movement into and out of cells",
        ),
    ),
    Topic(
        code="bi05",
        number=5,
        name="The mitotic cell cycle",
        blurb=(
            "Chromosome structure: DNA, histone proteins, sister chromatids, "
            "centromere, telomeres. The importance of mitosis in producing "
            "genetically identical daughter cells during growth of "
            "multicellular organisms, replacement of damaged or dead cells, "
            "tissue repair and asexual reproduction. The mitotic cell cycle: "
            "interphase (growth in G1 and G2, DNA replication in S phase), "
            "mitosis and cytokinesis; the role of telomeres in preventing gene "
            "loss from chromosome ends during replication; the role of stem "
            "cells in cell replacement and tissue repair by mitosis; how "
            "uncontrolled cell division can form a tumour. Chromosome behaviour "
            "in plant and animal cells during the mitotic cell cycle and the "
            "associated behaviour of the nuclear envelope, cell surface "
            "membrane and spindle, including the named stages prophase, "
            "metaphase, anaphase and telophase; interpreting photomicrographs, "
            "diagrams and microscope slides to identify the stage of the "
            "mitotic cell cycle shown."
        ),
        subsections=(
            "5.1 Replication and division of nuclei and cells",
            "5.2 Chromosome behaviour in mitosis",
        ),
    ),
    Topic(
        code="bi06",
        number=6,
        name="Nucleic acids and protein synthesis",
        blurb=(
            "Nucleotide structure, including the phosphorylated nucleotide ATP; "
            "purine bases adenine and guanine (double ring) versus pyrimidine "
            "bases cytosine, thymine and uracil (single ring). DNA structure as "
            "a double helix: complementary base pairing between antiparallel "
            "5'-to-3' and 3'-to-5' strands, the different hydrogen bonding of "
            "C-G versus A-T pairs, and phosphodiester bonds linking nucleotides. "
            "Semi-conservative DNA replication during S phase: the roles of DNA "
            "polymerase and DNA ligase, and the difference between leading- and "
            "lagging-strand replication arising from DNA polymerase adding "
            "nucleotides only 5' to 3'. RNA structure, using mRNA as the "
            "example. A gene as a nucleotide sequence coding for a polypeptide; "
            "the universal genetic code in which base triplets code for amino "
            "acids or act as start/stop codons. Transcription and translation: "
            "the roles of RNA polymerase, mRNA, codons, tRNA, anticodons and "
            "ribosomes; the transcribed (template) strand versus the "
            "non-transcribed strand; in eukaryotes, removal of introns and "
            "joining of exons to form mature mRNA from the primary transcript. "
            "Gene mutation as a change in DNA base sequence -- substitution, "
            "deletion or insertion of nucleotides -- and how each may alter the "
            "polypeptide produced."
        ),
        subsections=(
            "6.1 Structure of nucleic acids and replication of DNA",
            "6.2 Protein synthesis",
        ),
    ),
    Topic(
        code="bi07",
        number=7,
        name="Transport in plants",
        blurb=(
            "Plan diagrams of transverse sections of stems, roots and leaves of "
            "herbaceous dicotyledonous plants; the distribution of xylem and "
            "phloem in each; drawing and labelling xylem vessel elements, "
            "phloem sieve tube elements and companion cells from slides, "
            "photomicrographs and electron micrographs, and relating their "
            "structure to function. Water transport from soil to xylem via the "
            "apoplast pathway (lignin, cellulose) and the symplast pathway "
            "(endodermis, Casparian strip, suberin). Transpiration as "
            "evaporation of water from internal leaf surfaces followed by "
            "diffusion of water vapour to the atmosphere; hydrogen bonding of "
            "water molecules explaining cohesion-tension movement of water in "
            "the xylem and adhesion to cellulose cell walls. Annotated drawings "
            "of xerophyte leaf transverse sections to explain adaptations that "
            "reduce transpirational water loss. Movement of assimilates (e.g. "
            "sucrose, amino acids) dissolved in water from source to sink in "
            "phloem sieve tubes; how companion cells transfer assimilates into "
            "sieve tubes via proton pumps and cotransporter proteins; mass flow "
            "down a hydrostatic pressure gradient from source to sink."
        ),
        subsections=(
            "7.1 Structure of transport tissues",
            "7.2 Transport mechanisms",
        ),
    ),
    Topic(
        code="bi08",
        number=8,
        name="Transport in mammals",
        blurb=(
            "The mammalian circulatory system as a closed double circulation of "
            "heart, blood and blood vessels (arteries, arterioles, capillaries, "
            "venules, veins); the functions of the pulmonary artery, pulmonary "
            "vein, aorta and vena cava. Recognising arteries, veins and "
            "capillaries from slides, photomicrographs and electron "
            "micrographs, and how the structure of muscular arteries, elastic "
            "arteries, veins and capillaries relates to function. Recognising "
            "red blood cells, monocytes, neutrophils and lymphocytes. Water as "
            "the main component of blood and tissue fluid, and its solvent "
            "action and high specific heat capacity in transport; the "
            "functions and formation of tissue fluid in a capillary network. "
            "Oxygen and carbon dioxide transport: the roles of haemoglobin, "
            "carbonic anhydrase, haemoglobinic acid and carbaminohaemoglobin; "
            "the chloride shift and its importance; the role of plasma in "
            "carbon dioxide transport; the oxygen dissociation curve of adult "
            "haemoglobin and its importance at the partial pressures of oxygen "
            "found in the lungs versus respiring tissues; the Bohr shift and "
            "its importance. The heart: external and internal structure; wall "
            "thickness differences between atria/ventricles and between left/ "
            "right ventricle; the cardiac cycle, including the relationship "
            "between blood pressure changes during systole/diastole and valve "
            "opening/closing; the roles of the sinoatrial node, atrioventricular "
            "node and Purkyne tissue. (Haemoglobin's molecular structure belongs "
            "to Biological molecules; this topic covers its transport function.)"
        ),
        subsections=(
            "8.1 The circulatory system",
            "8.2 Transport of oxygen and carbon dioxide",
            "8.3 The heart",
        ),
    ),
    Topic(
        code="bi09",
        number=9,
        name="Gas exchange",
        blurb=(
            "The structure of the human gas exchange system: lungs, trachea, "
            "bronchi, bronchioles, alveoli, capillary network. The distribution "
            "in the gas exchange system of cartilage, ciliated epithelium, "
            "goblet cells, squamous epithelium of alveoli, smooth muscle and "
            "capillaries, and recognising each in slides, photomicrographs and "
            "electron micrographs; plan diagrams of transverse sections of the "
            "trachea and bronchus walls. The functions of ciliated epithelial "
            "cells, goblet cells and mucous glands in maintaining gas exchange "
            "system health; the functions of cartilage, smooth muscle, elastic "
            "fibres and squamous epithelium. Gas exchange between air in the "
            "alveoli and blood in the surrounding capillaries. (General "
            "diffusion theory and membrane structure belong to Cell membranes "
            "and transport; this topic is specifically the gas exchange organ "
            "system's structure and function.)"
        ),
        subsections=("9.1 The gas exchange system",),
    ),
    Topic(
        code="bi10",
        number=10,
        name="Infectious diseases",
        blurb=(
            "Infectious diseases as caused by transmissible pathogens. Four "
            "named diseases and their causative pathogens: cholera (the "
            "bacterium Vibrio cholerae), malaria (the protoctists Plasmodium "
            "falciparum, P. malariae, P. ovale and P. vivax), tuberculosis (the "
            "bacteria Mycobacterium tuberculosis and M. bovis) and HIV/AIDS (the "
            "human immunodeficiency virus). How each of cholera, malaria, TB and "
            "HIV is transmitted, and the biological, social and economic "
            "factors relevant to preventing and controlling them (the malarial "
            "parasite's life cycle is not required). Antibiotics: how "
            "penicillin acts on bacteria and why antibiotics do not affect "
            "viruses; the consequences of antibiotic resistance and steps that "
            "can reduce its impact."
        ),
        subsections=(
            "10.1 Infectious diseases",
            "10.2 Antibiotics",
        ),
    ),
    Topic(
        code="bi11",
        number=11,
        name="Immunity",
        blurb=(
            "The mode of action of phagocytes (macrophages and neutrophils). "
            "Antigens, and the difference between self and non-self antigens. "
            "The sequence of events in a primary immune response, including the "
            "roles of macrophages, B-lymphocytes (including plasma cells) and "
            "T-lymphocytes (T-helper cells and T-killer cells). The role of "
            "memory cells in the secondary immune response and long-term "
            "immunity. Relating antibody molecular structure to function; the "
            "hybridoma method for producing monoclonal antibodies, and their "
            "use in disease diagnosis and treatment. The differences between "
            "active and passive immunity, and between natural and artificial "
            "immunity. Vaccines as containing antigens that stimulate an immune "
            "response for long-term immunity, and how vaccination programmes "
            "help control the spread of infectious disease."
        ),
        subsections=(
            "11.1 The immune system",
            "11.2 Antibodies and vaccination",
        ),
    ),
)


# --- 9708 Papers 1 & 2: Economics (AS Level syllabus sections 1-6) -----------

_ECONOMICS_TOPICS: tuple[Topic, ...] = (
    Topic(
        code="ec01",
        number=1,
        name="Basic economic ideas and resource allocation",
        blurb=(
            "The fundamental economic problem of scarcity and the need to make "
            "choices at all levels -- individuals, firms, governments; the "
            "nature and definition of opportunity cost arising from choices; "
            "the basic questions of resource allocation (what, how, and for "
            "whom to produce). Economic methodology: economics as a social "
            "science, the distinction between positive statements (facts) and "
            "normative statements (value judgements), the meaning of ceteris "
            "paribus, and the importance of the time period (short run, long "
            "run, very long run). Factors of production -- land, labour, "
            "capital and enterprise -- their definitions and rewards, the "
            "difference between human and physical capital, division of "
            "labour and specialisation, and the entrepreneur's role in "
            "risk-bearing and organising the other factors. Decision-making "
            "and resource allocation in market, planned and mixed economic "
            "systems. Production possibility curves (PPCs): their meaning, "
            "the shape implied by constant versus increasing opportunity "
            "costs, the causes and consequences of shifts in a PPC, and the "
            "significance of a position within the curve. Classification of "
            "goods and services: free goods versus private (economic) goods, "
            "public goods, merit goods (under-consumed because of imperfect "
            "information) and demerit goods (over-consumed for the same "
            "reason)."
        ),
        subsections=(
            "1.1 Scarcity, choice and opportunity cost",
            "1.2 Economic methodology",
            "1.3 Factors of production",
            "1.4 Resource allocation in different economic systems",
            "1.5 Production possibility curves",
            "1.6 Classification of goods and services",
        ),
    ),
    Topic(
        code="ec02",
        number=2,
        name="The price system and the microeconomy",
        blurb=(
            "Effective demand; individual and market demand and supply; the "
            "determinants of demand and of supply; the causes of a shift in "
            "the demand curve versus the supply curve, and the distinction "
            "between a shift in a curve and a movement along it. Price "
            "elasticity of demand (PED), income elasticity of demand (YED) "
            "and cross elasticity of demand (XED): their definitions, "
            "formulae and calculation; the significance of the size and sign "
            "of each coefficient; descriptions of elasticity values "
            "(perfectly elastic, highly elastic, unitary, highly inelastic, "
            "perfectly inelastic); how PED varies along a straight-line "
            "demand curve; the factors affecting each elasticity; the "
            "relationship between PED and total expenditure on a product; "
            "and the implications of these elasticities for decision-making. "
            "Price elasticity of supply (PES): its definition, formula, "
            "calculation, the factors affecting it, and its implications for "
            "how quickly and easily firms react to changed market "
            "conditions. Market equilibrium and disequilibrium; the effects "
            "of shifts in demand and supply on equilibrium price and "
            "quantity; relationships between markets -- joint demand "
            "(complements), alternative demand (substitutes), derived demand "
            "and joint supply; the functions of price in resource allocation "
            "(rationing, signalling, incentivising). Consumer surplus and "
            "producer surplus: their meaning and significance, and how "
            "elasticity of demand and supply affects the extent of changes "
            "in each. (Elasticity calculations and demand/supply diagrams "
            "belong here; a specific tax or subsidy's effect on who bears "
            "the incidence of a price change belongs to Government "
            "microeconomy intervention.)"
        ),
        subsections=(
            "2.1 Demand and supply curves",
            "2.2 Price elasticity, income elasticity and cross elasticity of demand",
            "2.3 Price elasticity of supply",
            "2.4 The interaction of demand and supply",
            "2.5 Consumer and producer surplus",
        ),
    ),
    Topic(
        code="ec03",
        number=3,
        name="Government microeconomy intervention",
        blurb=(
            "Reasons for government intervention in individual markets: "
            "addressing the non-provision of public goods, addressing the "
            "over-consumption of demerit goods and the under-consumption of "
            "merit goods, and controlling prices in markets. Methods and "
            "effects of intervention: the impact and incidence of specific "
            "indirect taxes and of subsidies (including which side of the "
            "market bears more of the burden, depending on elasticity), "
            "direct provision of goods and services, maximum and minimum "
            "prices, buffer stock schemes, and the provision of information. "
            "Addressing income and wealth inequality: the distinction "
            "between income as a flow and wealth as a stock; measuring "
            "inequality (including the Gini coefficient, calculation not "
            "required); the economic reasons why income and wealth "
            "inequality arise; and policies to redistribute income and "
            "wealth -- the minimum wage, transfer payments, progressive "
            "income, inheritance and capital taxes, and state provision of "
            "essential goods and services. (The general definitions of "
            "indirect taxes and subsidies as tools and their incidence "
            "within one market belong here; how such taxes fit into the "
            "government's overall budget belongs to Government "
            "macroeconomic intervention.)"
        ),
        subsections=(
            "3.1 Reasons for government intervention in markets",
            "3.2 Methods and effects of government intervention in markets",
            "3.3 Addressing income and wealth inequality",
        ),
    ),
    Topic(
        code="ec04",
        number=4,
        name="The Macroeconomy",
        blurb=(
            "National income statistics: the meaning of national income and "
            "its measurement via Gross Domestic Product (GDP), Gross "
            "National Income (GNI) and Net National Income (NNI); adjusting "
            "measures from market prices to basic prices and from gross to "
            "net values. The circular flow of income in a closed and an open "
            "economy -- the flow between households, firms, government and "
            "the international economy; injections and leakages (the "
            "multiplier is not required); equilibrium and disequilibrium in "
            "the flow. Aggregate Demand (AD) and Aggregate Supply (AS) "
            "analysis: the definition and components of AD (AD = C + I + G + "
            "(X - M)) and its determinants; the shape of and causes of "
            "shifts in the AD curve; the definition, determinants and shape "
            "of the AS curve in the short run (SRAS) and long run (LRAS); "
            "causes of shifts in SRAS and LRAS; the distinction between a "
            "movement along and a shift in AD or AS; and how AD/AS "
            "equilibrium determines real output, the price level and "
            "employment. Economic growth: its meaning, measurement, the "
            "distinction between nominal and real GDP growth, and its causes "
            "and consequences. Unemployment: its meaning, measures (with "
            "reference to difficulties in measurement), causes and types "
            "(frictional, structural, cyclical, seasonal, technological), "
            "and consequences. Price stability: the definitions of "
            "inflation, deflation and disinflation; measuring price-level "
            "changes via the consumer price index (CPI) and the "
            "difficulties in doing so; the distinction between nominal "
            "(money) and real values; the causes of inflation (cost-push and "
            "demand-pull); and its consequences. (This topic is the "
            "underlying national-income measures and the AD/AS model "
            "itself; using that model to analyse the impact of a specific "
            "fiscal, monetary or supply-side policy belongs to Government "
            "macroeconomic intervention.)"
        ),
        subsections=(
            "4.1 National income statistics",
            "4.2 Introduction to the circular flow of income",
            "4.3 Aggregate Demand and Aggregate Supply analysis",
            "4.4 Economic growth",
            "4.5 Unemployment",
            "4.6 Price stability",
        ),
    ),
    Topic(
        code="ec05",
        number=5,
        name="Government macroeconomic intervention",
        blurb=(
            "Government macroeconomic policy objectives: price stability, "
            "low unemployment and economic growth (policy conflicts and "
            "trade-offs are not required). Fiscal policy: the meaning of a "
            "government budget, the distinction between a budget deficit and "
            "a budget surplus, the meaning and significance of the national "
            "debt; taxation -- types of tax (direct/indirect, "
            "progressive/regressive/proportional), rates of tax (marginal "
            "and average rates), and reasons for taxation; government "
            "spending -- capital (investment) versus current spending, and "
            "reasons for it; the distinction between expansionary and "
            "contractionary fiscal policy; and AD/AS analysis of the impact "
            "of expansionary or contractionary fiscal policy on equilibrium "
            "national income, real output, the price level and employment. "
            "Monetary policy: its definition; its tools -- interest rates, "
            "the money supply and credit regulations; the distinction "
            "between expansionary and contractionary monetary policy; and "
            "AD/AS analysis of its impact. Supply-side policy: its meaning "
            "in terms of its effect on the LRAS curve; its objectives of "
            "increasing productivity and productive capacity; its tools (for "
            "example training, infrastructure development, support for "
            "technological improvement); and AD/AS analysis of its impact. "
            "(The definitions of specific indirect taxes and subsidies as "
            "market-intervention tools, and their impact within one market, "
            "belong to Government microeconomy intervention; this topic is "
            "fiscal, monetary and supply-side policy at the level of the "
            "whole economy.)"
        ),
        subsections=(
            "5.1 Government macroeconomic policy objectives",
            "5.2 Fiscal policy",
            "5.3 Monetary policy",
            "5.4 Supply-side policy",
        ),
    ),
    Topic(
        code="ec06",
        number=6,
        name="International economic issues",
        blurb=(
            "The reasons for international trade: the distinction between "
            "absolute and comparative advantage; the benefits of "
            "specialisation and free trade (trade liberalisation), including "
            "the trading possibility curve; exports, imports and the terms "
            "of trade -- their measurement and the causes and impact of "
            "changes in them; and the limitations of the theories of "
            "absolute and comparative advantage. Protectionism: its meaning "
            "in the context of international trade; the different tools of "
            "protection and their impact -- tariffs, import quotas, export "
            "subsidies, embargoes and excessive administrative burdens ('red "
            "tape'); and the arguments for and against protectionism. The "
            "current account of the balance of payments: its components "
            "(trade in goods, trade in services, primary income and "
            "secondary income), the definition of balance and of imbalances "
            "(deficit and surplus); calculating the balance of trade in "
            "goods, in services, in goods and services, and the current "
            "account balance (CAB); and the causes and consequences of "
            "current-account imbalances for the domestic and external "
            "economy. Exchange rates: the definition of an exchange rate; "
            "the determination of a floating exchange rate; the distinction "
            "between depreciation and appreciation; the causes of changes in "
            "a floating exchange rate (demand and supply of the currency); "
            "and AD/AS analysis of the impact of exchange-rate changes on "
            "the domestic economy's equilibrium national income, real "
            "output, the price level and employment. Policies to correct "
            "current-account imbalances: the government policy objective of "
            "current-account stability, and the effect of fiscal, monetary, "
            "supply-side and protectionist policies on the current account."
        ),
        subsections=(
            "6.1 The reasons for international trade",
            "6.2 Protectionism",
            "6.3 Current account of the balance of payments",
            "6.4 Exchange rates",
            "6.5 Policies to correct imbalances in the current account of the balance of payments",
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
# A Level papers (P1/P4 above are AS Level). Each is its own single-paper
# subject, same shape as FURTHER_PURE_1/FURTHER_PROB_STATS -- disjoint
# syllabus content, not one taxonomy spanning several papers.
FURTHER_PURE_2 = Taxonomy(
    key="9231p2",
    subject_code="9231",
    papers=(2,),
    subject_name="Further Pure Mathematics 2",
    topics=_FURTHER_PURE_2_TOPICS,
)
FURTHER_MECHANICS = Taxonomy(
    key="9231p3",
    subject_code="9231",
    papers=(3,),
    subject_name="Further Mechanics",
    topics=_FURTHER_MECHANICS_TOPICS,
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
# A Level papers (P1/P5 above are AS Level). Each is its own single-paper
# subject, same shape as PURE_MATH_1/PROB_STATS_1 -- disjoint syllabus content,
# not one taxonomy spanning several papers.
PURE_MATH_3 = Taxonomy(
    key="9709p3",
    subject_code="9709",
    papers=(3,),
    subject_name="Pure Mathematics 3",
    topics=_PURE_MATH_3_TOPICS,
)
MECHANICS = Taxonomy(
    key="9709p4",
    subject_code="9709",
    papers=(4,),
    subject_name="Mechanics",
    topics=_MECHANICS_TOPICS,
)
PROB_STATS_2 = Taxonomy(
    key="9709p6",
    subject_code="9709",
    papers=(6,),
    subject_name="Probability & Statistics 2",
    topics=_PROB_STATS_2_TOPICS,
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
# Same shape as CHEMISTRY -- one taxonomy spans both papers.
BIOLOGY = Taxonomy(
    key="9700",
    subject_code="9700",
    papers=(1, 2),
    subject_name="Biology",
    topics=_BIOLOGY_TOPICS,
)
# Same shape as CHEMISTRY/BIOLOGY -- one taxonomy spans both papers. Coarser
# than the others (6 topics, not 11-22) since that's the AS syllabus's own
# top-level section count for Economics ("topics 1.1-6.5").
ECONOMICS = Taxonomy(
    key="9708",
    subject_code="9708",
    papers=(1, 2),
    subject_name="Economics",
    topics=_ECONOMICS_TOPICS,
)

_COMPUTER_SCIENCE_TOPICS: tuple[Topic, ...] = (
    Topic(
        code="cs01",
        number=1,
        name="Information representation",
        blurb=(
            "Binary magnitudes and the difference between binary prefixes (kibi, mebi, "
            "gibi, tebi) and decimal prefixes (kilo, mega, giga, tera). Binary, denary, "
            "hexadecimal, Binary Coded Decimal (BCD) and one's/two's complement; "
            "converting between number bases; binary addition and subtraction and "
            "overflow; uses of BCD and hexadecimal. Character sets: ASCII, extended ASCII "
            "and Unicode. Bitmap images (pixel, file header, image/screen resolution, "
            "colour/bit depth, file-size calculations) versus vector graphics (drawing "
            "object, property, drawing list). Sound: sampling, sampling rate and "
            "resolution, analogue versus digital. Lossy and lossless compression, "
            "including run-length encoding (RLE)."
        ),
        subsections=(
            "1.1 Data Representation",
            "1.2 Multimedia – Graphics, Sound",
            "1.3 Compression",
        ),
        papers=(1,),
    ),
    Topic(
        code="cs02",
        number=2,
        name="Communication",
        blurb=(
            "Networks and the internet: LAN versus WAN; client-server and peer-to-peer "
            "models; thin and thick clients; bus, star, mesh and hybrid topologies and how "
            "packets travel between hosts; public and private cloud computing. Wired "
            "versus wireless media (copper, fibre-optic, radio/WiFi, microwave, "
            "satellite). LAN hardware: switch, server, NIC, WNIC, WAP, bridge, repeater, "
            "router. Ethernet and CSMA/CD collision handling. Real-time and on-demand bit "
            "streaming and bit rates. The WWW versus the internet and internet hardware "
            "(modems, PSTN, dedicated lines, cell networks). IPv4 and IPv6 addresses, "
            "subnetting, public/private and static/dynamic IP addresses; URLs and DNS."
        ),
        subsections=("2.1 Networks including the internet",),
        papers=(1,),
    ),
    Topic(
        code="cs03",
        number=3,
        name="Hardware",
        blurb=(
            "Input, output, primary memory and secondary storage; embedded systems. How "
            "devices work: laser and 3D printers, microphone, speakers, magnetic hard "
            "disk, solid-state (flash) memory, optical discs, touchscreens, VR headsets. "
            "Buffers. RAM versus ROM, SRAM versus DRAM, PROM/EPROM/EEPROM. Monitoring "
            "versus control systems with sensors, actuators and feedback. Logic gates "
            "NOT, AND, OR, NAND, NOR, XOR and their truth tables; constructing a logic "
            "circuit, a truth table or a logic expression from a problem statement, a "
            "circuit, an expression or a truth table."
        ),
        subsections=(
            "3.1 Computers and their components",
            "3.2 Logic Gates and Logic Circuits",
        ),
        papers=(1,),
    ),
    Topic(
        code="cs04",
        number=4,
        name="Processor Fundamentals",
        blurb=(
            "Von Neumann architecture and the stored program concept; general and special "
            "purpose registers (PC, MDR, MAR, ACC, IX, CIR, status register); ALU, control "
            "unit, system clock, IAS; address, data and control buses; performance factors "
            "(cores, bus width, clock speed, cache); USB, HDMI and VGA ports. The "
            "fetch-execute cycle in register transfer notation; interrupts and interrupt "
            "service routines. Assembly language versus machine code, the two-pass "
            "assembler, tracing assembly programs using the given instruction set "
            "(LDM, LDD, LDI, LDX, STO, ADD, CMP, JPE, JPN, IN, OUT ...), instruction "
            "groups and addressing modes (immediate, direct, indirect, indexed, "
            "relative). Binary shifts (logical, arithmetic, cyclic) and bit masking with "
            "AND, OR, XOR, LSL, LSR to test and set bits."
        ),
        subsections=(
            "4.1 Central Processing Unit (CPU) Architecture",
            "4.2 Assembly Language",
            "4.3 Bit manipulation",
        ),
        papers=(1,),
    ),
    Topic(
        code="cs05",
        number=5,
        name="System Software",
        blurb=(
            "Why a computer needs an operating system and its management tasks (memory, "
            "file, security, hardware/peripheral and process management); utility software "
            "(disk formatter, virus checker, defragmenter, disk repair, compression, "
            "back-up); program libraries and DLL files. Language translators: assembler, "
            "compiler and interpreter, their benefits and drawbacks, and partially "
            "compiled/interpreted languages such as Java. IDE features for coding "
            "(context-sensitive prompts), error detection (dynamic syntax checks), "
            "presentation (prettyprint, collapsing blocks) and debugging (single "
            "stepping, breakpoints, variable watch/report windows)."
        ),
        subsections=("5.1 Operating Systems", "5.2 Language Translators"),
        papers=(1,),
    ),
    Topic(
        code="cs06",
        number=6,
        name="Security, privacy and data integrity",
        blurb=(
            "The difference between security, privacy and integrity of data. Security "
            "measures for systems and networks: user accounts, passwords, digital "
            "signatures, biometrics, firewalls, anti-virus and anti-spyware, encryption, "
            "access rights. Threats such as malware (viruses, spyware), hackers, "
            "phishing and pharming, and ways to reduce the risk. Data validation (range, "
            "format, length, presence, existence, limit checks, check digits) and "
            "verification during entry (visual check, double entry) and transfer (parity "
            "check by byte and block, checksum)."
        ),
        subsections=("6.1 Data Security", "6.2 Data Integrity"),
        papers=(1,),
    ),
    Topic(
        code="cs07",
        number=7,
        name="Ethics and Ownership",
        blurb=(
            "Ethics for computing professionals and professional bodies such as the BCS "
            "and IEEE; acting ethically or unethically in a given situation and its "
            "impact. Copyright legislation. Software licensing -- Free Software "
            "Foundation, Open Source Initiative, shareware, commercial -- and justifying a "
            "licence for a situation. Artificial Intelligence: its applications and its "
            "social, economic and environmental impact."
        ),
        subsections=("7.1 Ethics and Ownership",),
        papers=(1,),
    ),
    Topic(
        code="cs08",
        number=8,
        name="Databases",
        blurb=(
            "Limitations of a file-based approach and how relational databases address "
            "them. Relational terminology: entity, table, record, field, tuple, attribute, "
            "primary/candidate/secondary/foreign keys, one-to-one/one-to-many/many-to-many "
            "relationships, referential integrity, indexing; E-R diagrams. Normalisation "
            "to 1NF, 2NF and 3NF. DBMS features (data dictionary, data modelling, logical "
            "schema, integrity, security, backups, access rights), developer interface "
            "and query processor. SQL: DDL (CREATE DATABASE, CREATE TABLE with data types, "
            "ALTER TABLE, PRIMARY KEY, FOREIGN KEY) and DML queries (SELECT, WHERE, ORDER "
            "BY, GROUP BY, INNER JOIN, SUM, COUNT, AVG) and maintenance (INSERT INTO, "
            "DELETE FROM, UPDATE)."
        ),
        subsections=(
            "8.1 Database Concepts",
            "8.2 Database Management Systems (DBMS)",
            "8.3 Data Definition Language (DDL) and Data Manipulation Language (DML)",
        ),
        papers=(1,),
    ),
    Topic(
        code="cs09",
        number=9,
        name="Algorithm Design and Problem-solving",
        blurb=(
            "Computational thinking: abstraction (producing an abstract model with only "
            "the essential details) and decomposition into sub-problems and program "
            "modules. Algorithms as sequences of defined steps; identifier tables; "
            "pseudocode with input, process and output using sequence, selection and "
            "iteration; documenting an algorithm as structured English, a flowchart or "
            "pseudocode and converting between them; stepwise refinement; logic "
            "statements that define parts of a solution. Typically: describe or complete "
            "an algorithm, draw or interpret a program flowchart."
        ),
        subsections=("9.1 Computational Thinking Skills", "9.2 Algorithms"),
        papers=(2,),
    ),
    Topic(
        code="cs10",
        number=10,
        name="Data Types and Structures",
        blurb=(
            "Choosing data types (INTEGER, REAL, CHAR, STRING, BOOLEAN, DATE); record "
            "structures and reading/writing their fields. 1D and 2D arrays: index, upper "
            "and lower bound, processing array data, bubble sort and linear search. Text "
            "files: why files are needed and pseudocode to read and write lines. Abstract "
            "data types -- stack, queue and linked list -- their features and uses, adding, "
            "editing and deleting data, and implementing them with arrays and pointers."
        ),
        subsections=(
            "10.1 Data Types and Records",
            "10.2 Arrays",
            "10.3 Files",
            "10.4 Introduction to Abstract Data Types (ADT)",
        ),
        papers=(2,),
    ),
    Topic(
        code="cs11",
        number=11,
        name="Programming",
        blurb=(
            "Writing pseudocode from a flowchart or structured English: constants, "
            "variable declarations, assignment, arithmetic and logical expressions, input "
            "and output; built-in functions and string manipulation. Constructs: IF/ELSE "
            "and nested IF, CASE, count-controlled, pre-condition and post-condition "
            "loops, and justifying the choice of loop. Structured programming: defining "
            "and calling procedures and functions, parameters passed by value or by "
            "reference, headers, interfaces, arguments and return values; writing "
            "efficient pseudocode. Typically: write or complete a pseudocode module."
        ),
        subsections=(
            "11.1 Programming Basics",
            "11.2 Constructs",
            "11.3 Structured Programming",
        ),
        papers=(2,),
    ),
    Topic(
        code="cs12",
        number=12,
        name="Software Development",
        blurb=(
            "Program development life cycles (waterfall, iterative, RAD) with their "
            "benefits and drawbacks, and the analysis, design, coding, testing and "
            "maintenance stages. Program design with structure charts (modules and the "
            "parameters passed between them, deriving pseudocode from a chart) and "
            "state-transition diagrams. Syntax, logic and run-time errors and correcting "
            "them; testing methods (dry run and trace tables, walkthrough, white-box, "
            "black-box, integration, alpha, beta, acceptance, stub testing); test "
            "strategies, test plans and normal/abnormal/extreme/boundary test data; "
            "perfective, adaptive and corrective maintenance."
        ),
        subsections=(
            "12.1 Program Development Life cycle",
            "12.2 Program Design",
            "12.3 Program Testing and Maintenance",
        ),
        papers=(2,),
    ),
)

# Same shape as PHYSICS -- one taxonomy spans both papers -- but each topic's
# `papers` restricts it to the one paper the syllabus says examines it.
COMPUTER_SCIENCE = Taxonomy(
    key="9618",
    subject_code="9618",
    papers=(1, 2),
    subject_name="Computer Science",
    topics=_COMPUTER_SCIENCE_TOPICS,
)

TAXONOMIES: tuple[Taxonomy, ...] = (
    PHYSICS,
    FURTHER_PURE_1,
    FURTHER_PROB_STATS,
    FURTHER_PURE_2,
    FURTHER_MECHANICS,
    PURE_MATH_1,
    PROB_STATS_1,
    PURE_MATH_3,
    MECHANICS,
    PROB_STATS_2,
    CHEMISTRY,
    BIOLOGY,
    ECONOMICS,
    COMPUTER_SCIENCE,
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
