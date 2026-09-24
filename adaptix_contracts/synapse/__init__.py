"""Adaptix Synapse Fabric canonical contracts (SYN-001).

LAW SYN-001: integrate capabilities, not manufacturers. Manufacturer and
protocol differences terminate at the Adaptix driver layer (transport and
protocol drivers in Adaptix-Integrations-Service ``connector_sdk``); above it
only these versioned capability, signal, evidence, session, provenance and
edge contracts exist. Nothing in this package names a manufacturer as a type,
and nothing expresses a command to a medical device: the medical-device
command plane is forbidden in v1.

Pipeline these contracts carry, end to end::

    Physical Source -> Synapse Edge -> Transport Driver -> Protocol Driver
    -> Device Genome -> Signal Compiler -> Evidence Ledger -> Device Truth
    -> Care Session Binder (ePCR) -> ePCR projection / downstream

This package defines shapes only; it runs no Synapse behaviour.

Import each name from the module that defines it; that module's ``__all__`` is
the single declaration of its public surface, and this package root
deliberately re-lists nothing::

    from adaptix_contracts.synapse.signals import ClinicalSignalEnvelope
    from adaptix_contracts.synapse.devices import DeviceGenome
    from adaptix_contracts.synapse.edge import EdgeBatch, EdgeBatchAck

Modules: ``enums`` (vocabulary), ``signals`` (envelope and payloads),
``devices`` (genome, capability profile, driver packs), ``sessions``,
``evidence`` (ledger references, upload authorization), ``provenance`` (value
shapes, lineage, replay), ``edge`` (Synapse Edge protocol).
"""
