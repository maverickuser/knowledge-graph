"""Canonical JEE Physics syllabus taxonomy used to seed graph coverage."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TopicSpec:
    title: str
    concepts: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ChapterSpec:
    title: str
    topics: tuple[TopicSpec, ...]


PHYSICS_SYLLABUS: tuple[ChapterSpec, ...] = (
    ChapterSpec(
        "Units and Measurements",
        (
            TopicSpec("Physical quantities and units", ("SI units", "fundamental units", "derived units")),
            TopicSpec("Dimensional analysis", ("dimensions", "dimensional homogeneity", "dimensional formulae")),
            TopicSpec("Errors and measurements", ("least count", "significant figures", "absolute error", "percentage error")),
        ),
    ),
    ChapterSpec(
        "Kinematics",
        (
            TopicSpec("Motion in a straight line", ("position", "displacement", "velocity", "acceleration")),
            TopicSpec("Motion in a plane", ("vectors", "relative velocity", "projectile motion", "uniform circular motion")),
            TopicSpec("Graphs of motion", ("position-time graph", "velocity-time graph", "area under graph", "slope of graph")),
        ),
    ),
    ChapterSpec(
        "Laws of Motion",
        (
            TopicSpec("Newton's laws", ("inertia", "force", "free body diagram", "normal reaction")),
            TopicSpec("Friction", ("static friction", "kinetic friction", "limiting friction", "angle of repose")),
            TopicSpec("Circular dynamics", ("centripetal force", "banking of roads", "conical pendulum")),
        ),
    ),
    ChapterSpec(
        "Work, Energy and Power",
        (
            TopicSpec("Work and power", ("work done", "power", "work-energy theorem")),
            TopicSpec("Energy conservation", ("kinetic energy", "potential energy", "mechanical energy conservation")),
            TopicSpec("Collisions", ("linear momentum", "elastic collision", "inelastic collision", "coefficient of restitution")),
        ),
    ),
    ChapterSpec(
        "Rotational Mechanics",
        (
            TopicSpec("Rotational kinematics", ("angular displacement", "angular velocity", "angular acceleration")),
            TopicSpec("Torque and angular momentum", ("torque", "angular momentum", "conservation of angular momentum")),
            TopicSpec("Moment of inertia", ("moment of inertia", "parallel-axis theorem", "perpendicular-axis theorem")),
            TopicSpec("Rolling motion", ("rolling without slipping", "rotational kinetic energy", "instantaneous axis")),
        ),
    ),
    ChapterSpec(
        "Gravitation",
        (
            TopicSpec("Universal gravitation", ("gravitational force", "gravitational field", "gravitational potential")),
            TopicSpec("Planetary motion", ("kepler laws", "orbital velocity", "time period of satellite")),
            TopicSpec("Escape and satellites", ("escape velocity", "binding energy", "geostationary satellite")),
        ),
    ),
    ChapterSpec(
        "Properties of Matter",
        (
            TopicSpec("Elasticity", ("stress", "strain", "young modulus", "bulk modulus")),
            TopicSpec("Fluids", ("pressure", "buoyancy", "bernoulli principle", "viscosity")),
            TopicSpec("Surface tension", ("surface energy", "capillarity", "excess pressure")),
        ),
    ),
    ChapterSpec(
        "Thermal Properties of Matter",
        (
            TopicSpec("Thermal expansion", ("linear expansion", "area expansion", "volume expansion")),
            TopicSpec("Calorimetry", ("specific heat", "latent heat", "heat transfer")),
            TopicSpec("Kinetic temperature", ("temperature scales", "thermal equilibrium", "black body radiation")),
        ),
    ),
    ChapterSpec(
        "Thermodynamics",
        (
            TopicSpec("First law", ("internal energy", "heat", "work in thermodynamics", "first law of thermodynamics")),
            TopicSpec("Thermodynamic processes", ("isothermal process", "adiabatic process", "isobaric process", "isochoric process")),
            TopicSpec("Heat engines", ("second law of thermodynamics", "carnot engine", "efficiency")),
        ),
    ),
    ChapterSpec(
        "Kinetic Theory",
        (
            TopicSpec("Ideal gas model", ("ideal gas equation", "degrees of freedom", "equipartition of energy")),
            TopicSpec("Molecular speeds", ("rms speed", "mean free path", "pressure of ideal gas")),
        ),
    ),
    ChapterSpec(
        "Oscillations",
        (
            TopicSpec("Simple harmonic motion", ("restoring force", "time period", "phase", "amplitude")),
            TopicSpec("Spring and pendulum systems", ("spring constant", "simple pendulum", "energy in shm")),
            TopicSpec("Damped and forced oscillations", ("damping", "resonance", "forced oscillation")),
        ),
    ),
    ChapterSpec(
        "Waves",
        (
            TopicSpec("Wave motion", ("wavelength", "frequency", "wave speed", "phase difference")),
            TopicSpec("Sound waves", ("doppler effect", "beats", "intensity of sound")),
            TopicSpec("Standing waves", ("nodes", "antinodes", "organ pipes", "stretched string")),
        ),
    ),
    ChapterSpec(
        "Electrostatics",
        (
            TopicSpec("Electric charge and field", ("coulomb law", "electric field", "electric dipole", "field lines")),
            TopicSpec("Gauss law", ("electric flux", "gauss law", "symmetry in electrostatics")),
            TopicSpec("Potential and capacitance", ("electric potential", "potential energy", "capacitance", "capacitors in series and parallel")),
        ),
    ),
    ChapterSpec(
        "Current Electricity",
        (
            TopicSpec("Current and resistance", ("electric current", "drift velocity", "ohm law", "resistivity")),
            TopicSpec("DC circuits", ("kirchhoff laws", "wheatstone bridge", "meter bridge", "potentiometer")),
            TopicSpec("Instruments", ("galvanometer", "ammeter", "voltmeter", "shunt resistance")),
        ),
    ),
    ChapterSpec(
        "Moving Charges and Magnetism",
        (
            TopicSpec("Magnetic force", ("lorentz force", "cyclotron motion", "force on current carrying wire")),
            TopicSpec("Magnetic field due to current", ("biot-savart law", "ampere circuital law", "solenoid", "toroid")),
            TopicSpec("Moving coil instruments", ("moving coil galvanometer", "current sensitivity", "voltage sensitivity")),
        ),
    ),
    ChapterSpec(
        "Magnetism and Matter",
        (
            TopicSpec("Magnetic dipole", ("bar magnet", "magnetic dipole moment", "earth magnetism")),
            TopicSpec("Magnetic materials", ("diamagnetism", "paramagnetism", "ferromagnetism", "hysteresis")),
        ),
    ),
    ChapterSpec(
        "Electromagnetic Induction",
        (
            TopicSpec("Faraday law", ("magnetic flux", "induced emf", "faraday law", "lenz law")),
            TopicSpec("Inductance", ("self inductance", "mutual inductance", "energy in inductor")),
            TopicSpec("Motional emf", ("motional emf", "eddy currents", "induced electric field")),
        ),
    ),
    ChapterSpec(
        "Alternating Current",
        (
            TopicSpec("AC fundamentals", ("rms value", "phasor", "reactance", "impedance")),
            TopicSpec("LCR circuits", ("series lcr circuit", "resonance in ac", "power factor")),
            TopicSpec("Transformers", ("transformer", "step-up transformer", "step-down transformer")),
        ),
    ),
    ChapterSpec(
        "Electromagnetic Waves",
        (
            TopicSpec("Maxwell and EM waves", ("displacement current", "electromagnetic wave", "em spectrum")),
        ),
    ),
    ChapterSpec(
        "Ray Optics",
        (
            TopicSpec("Reflection and refraction", ("reflection", "refraction", "snell law", "total internal reflection")),
            TopicSpec("Mirrors and lenses", ("mirror formula", "lens formula", "magnification", "power of lens")),
            TopicSpec("Optical instruments", ("microscope", "telescope", "prism", "dispersion")),
        ),
    ),
    ChapterSpec(
        "Wave Optics",
        (
            TopicSpec("Interference", ("coherent sources", "young double slit experiment", "fringe width")),
            TopicSpec("Diffraction and polarization", ("single slit diffraction", "polarization", "brewster law")),
        ),
    ),
    ChapterSpec(
        "Dual Nature of Matter",
        (
            TopicSpec("Photoelectric effect", ("work function", "threshold frequency", "stopping potential")),
            TopicSpec("Matter waves", ("de broglie wavelength", "davisson germer experiment")),
        ),
    ),
    ChapterSpec(
        "Atoms and Nuclei",
        (
            TopicSpec("Atomic structure", ("bohr model", "energy levels", "hydrogen spectrum")),
            TopicSpec("Nuclear physics", ("nuclear binding energy", "radioactivity", "half life", "nuclear fission", "nuclear fusion")),
        ),
    ),
    ChapterSpec(
        "Semiconductor Electronics",
        (
            TopicSpec("Semiconductor devices", ("intrinsic semiconductor", "extrinsic semiconductor", "pn junction diode", "zener diode")),
            TopicSpec("Digital electronics", ("logic gates", "truth table", "rectifier", "transistor")),
        ),
    ),
)
