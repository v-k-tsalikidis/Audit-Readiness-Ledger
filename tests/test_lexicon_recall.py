"""Every signature in the lexicon has to be able to fire.

A signature that never matches anything is worse than no signature at all.
It does not appear in the report as a limitation; it appears as a control
nothing addresses, for every document set, forever. The reader has no way
to tell that from a real gap.

So each control gets one sentence of the kind a policy actually contains,
and the test asserts the control comes back addressed. The sentences are
also the clearest documentation of what each signature expects, which is
why they are written as prose rather than as keyword soup.

The second test is the one that found the problems. Each sentence is run
against all 93 signatures, not just its own, and any other control that
claims coverage is cross-talk. Some of it is honest -- a sentence about
outsourced development really does mention acceptance testing -- so those
pairs are declared. Anything undeclared fails.
"""

from __future__ import annotations

import unittest

from audit_readiness_ledger.lexicon_loader import load_framework, load_signatures
from audit_readiness_ledger.signatures import Coverage, Document, evaluate_all

FRAMEWORK = load_framework("iso-27001-2022")
SIGNATURES = load_signatures("iso-27001-2022", FRAMEWORK)

# One sentence per control, in the register a real policy is written in.
SENTENCES: dict[str, str] = {
    "A.5.1": "The information security policy is approved by the Managing Director and reviewed each year.",
    "A.5.2": "Roles and responsibilities for information security are assigned by the Head of IT.",
    "A.5.3": "Segregation of duties applies so that no single role can both request and approve a payment.",
    "A.5.4": "Top management requires all personnel to apply the rules set out here.",
    "A.5.5": "Contact with authorities is maintained through the Data Protection Officer.",
    "A.5.6": "The security manager holds membership of an industry forum and attends its meetings.",
    "A.5.7": "Threat intelligence is collected from two commercial feeds and analysed weekly.",
    "A.5.8": "Project management includes a security risk assessment at each milestone.",
    "A.5.9": "The asset register lists every server with an owner recorded against it.",
    "A.5.10": "Acceptable use of company equipment is limited to business purposes.",
    "A.5.11": "Return of assets is confirmed on the leaver's last working day.",
    "A.5.12": "Information is classified as Public, Internal or Confidential.",
    "A.5.13": "Documents are labelled with their classification in the footer.",
    "A.5.14": "Information transfer to third parties is encrypted and covered by a written agreement.",
    "A.5.15": "Access rights are granted on the business requirement to know and on least privilege.",
    "A.5.16": "Each user account has a unique identifier and is disabled when the person leaves.",
    "A.5.17": "Passwords must meet the complexity rule before they can be used.",
    "A.5.18": "Access rights are reviewed every six months and revoked when no longer needed.",
    "A.5.19": "Supplier security requirements are set before any contract is signed.",
    "A.5.20": "Supplier agreements include confidentiality clauses and a right to audit.",
    "A.5.21": "Risks in the ICT supply chain are assessed and requirements reach every subcontractor.",
    "A.5.22": "Supplier performance is reviewed at quarterly meetings and service reports are monitored.",
    "A.5.23": "Cloud services are covered by a shared responsibility matrix.",
    "A.5.24": "The incident response plan sets out roles and procedures before anything happens.",
    "A.5.25": "A security event is assessed within one hour and categorised as low, medium or high.",
    "A.5.26": "Incident response follows containment, then eradication, and every step is recorded.",
    "A.5.27": "A post-incident review captures lessons learned and the actions are tracked.",
    "A.5.28": "Where legal action may follow, evidence is preserved under a chain of custody record.",
    "A.5.29": "The business continuity plan states how information security is held during disruption.",
    "A.5.30": "The recovery time objective is four hours and disaster recovery is exercised yearly.",
    "A.5.31": "Legal requirements that apply to us are identified and kept in the compliance register.",
    "A.5.32": "Software licences are held for every product and unlicensed software is prohibited.",
    "A.5.33": "Records are kept for the retention period and protected from alteration.",
    "A.5.34": "Personal data is held only for the stated retention period.",
    "A.5.35": "An independent review of information security is carried out every two years.",
    "A.5.36": "Compliance with this policy is monitored by the Head of IT.",
    "A.5.37": "Standard operating procedures are documented and available to the staff who need them.",
    "A.6.1": "Screening of candidates is completed before employment starts.",
    "A.6.2": "The employment contract states security responsibilities and confidentiality obligations.",
    "A.6.3": "Security awareness training is given at induction and repeated annually for all staff.",
    "A.6.4": "The disciplinary process applies to any breach of this policy.",
    "A.6.5": "On termination, access to every system is removed the same day.",
    "A.6.6": "A non-disclosure agreement is signed by every contractor before work begins.",
    "A.6.7": "Remote working is permitted with a company laptop and the company VPN.",
    "A.6.8": "Staff must report a security event without delay through the service desk.",
    "A.7.1": "The depot has a fenced security perimeter around the whole site.",
    "A.7.2": "Physical entry needs an access badge, and visitors are escorted at all times.",
    "A.7.3": "The server room is locked and the key is held at reception.",
    "A.7.4": "CCTV covers the yard and the rest of the premises outside working hours.",
    "A.7.5": "Fire detection and flood sensors cover the server room.",
    "A.7.6": "Working in secure areas is supervised and photography is prohibited.",
    "A.7.7": "A clear desk is required at the end of each day.",
    "A.7.8": "Equipment siting keeps screens from being overlooked by visitors.",
    "A.7.9": "Assets taken off-premises need approval and the device must be encrypted.",
    "A.7.10": "Removable media must be encrypted and other USB devices are prohibited.",
    "A.7.11": "The uninterruptible power supply and the generator are tested twice a year.",
    "A.7.12": "Network cabling runs in conduit and patch panels are labelled.",
    "A.7.13": "Equipment maintenance follows the manufacturer's intervals.",
    "A.7.14": "Certificates of destruction are kept for every piece of equipment sent away.",
    "A.8.1": "Every laptop is encrypted and managed through the endpoint console.",
    "A.8.2": "Privileged access is held in separate admin accounts and reviewed each quarter.",
    "A.8.3": "Information access restriction limits each person to the function they perform.",
    "A.8.4": "Access to the source code repository is read-only outside the team.",
    "A.8.5": "Multi-factor authentication is needed at every login to the portal.",
    "A.8.6": "Capacity planning forecasts demand and thresholds are monitored.",
    "A.8.7": "Anti-virus is installed on every machine and definitions are updated daily.",
    "A.8.8": "Patching is applied within the timeframe set by severity.",
    "A.8.9": "A secure configuration baseline is documented for each server type.",
    "A.8.10": "Secure deletion is carried out once the retention period has passed.",
    "A.8.11": "Data masking is applied to personal data used outside production.",
    "A.8.12": "Data loss prevention controls are in place and outbound mail is monitored.",
    "A.8.13": "Backups run nightly and a restore is tested every quarter.",
    "A.8.14": "Redundancy is built into the architecture so that failover keeps the service up.",
    "A.8.15": "Audit logs are retained for one year and protected from alteration.",
    "A.8.16": "The SIEM raises an alert on anomalous network activity.",
    "A.8.17": "All servers take their time source from NTP so that logs line up.",
    "A.8.18": "Use of system utilities is restricted and every run is logged.",
    "A.8.19": "Software installation on operational systems is restricted to administrators.",
    "A.8.20": "Firewall rules are written down and reviewed twice a year.",
    "A.8.21": "Network services are covered by an agreement stating the security mechanisms in use.",
    "A.8.22": "The production network is segmented into VLANs and the DMZ is isolated.",
    "A.8.23": "Web filtering blocks malicious website categories.",
    "A.8.24": "Encryption is applied in transit and at rest under the key management policy.",
    "A.8.25": "The secure development life cycle sets the gates applied at each stage.",
    "A.8.26": "Application security requirements are documented and agreed before work starts.",
    "A.8.27": "Secure engineering principles including defence in depth are applied to every design.",
    "A.8.28": "Developers follow a secure coding standard based on OWASP.",
    "A.8.29": "Penetration testing is carried out before release.",
    "A.8.30": "Outsourced development is monitored against the requirements in the contract.",
    "A.8.31": "The development environment is separated from anything customers touch.",
    "A.8.32": "Every change request is approved and a rollback plan is recorded.",
    "A.8.33": "Test data is masked before it is copied out of production.",
    "A.8.34": "Audit testing is planned in advance and kept to read-only access.",
}
# Cross-talk that is honest rather than a defect: the sentence really does
# say something about the other control too. Each pair is a claim someone
# can check by reading the sentence.
ALLOWED_CROSSTALK: dict[str, set[str]] = {
    # A sentence about handing assets back on a leaver's last day is
    # genuinely about both. A.6.5 covers what a leaver still owes the
    # organisation; A.5.11 covers the assets themselves. A reader who
    # opens the line finds it says what both controls ask about.
    "A.5.11": {"A.6.5"},
    # "Access rights are granted on least privilege" is the subject of
    # A.5.18 as much as of A.5.15. One states the rule, the other governs
    # the granting. A policy sentence normally does both at once.
    "A.5.15": {"A.5.18"},
    # The sentence says the data is masked. A.8.11 is data masking. There
    # is no reading of it where only one of the two applies.
    "A.8.33": {"A.8.11"},
}


def evaluate_sentence(text: str) -> dict[str, Coverage]:
    document = Document("sample.md", (text,))
    return {f.control_id: f.coverage for f in evaluate_all(FRAMEWORK.ids, SIGNATURES, [document])}


class NoSignatureSatisfiesItselfWithOnePhrase(unittest.TestCase):
    """`required: 2` has to mean two things, not the same thing twice.

    A.5.33 had "retention period" in its subject group and "retention" in
    its supporting group. The phrase "retention period" satisfied both, so
    a control asking for a subject plus something done about it was really
    asking for the subject alone. Twenty-two signatures had this before it
    was noticed, some of them from the first draft of the lexicon.
    """

    def test_no_supporting_term_is_just_a_word_from_the_subject(self):
        for control_id, signature in SIGNATURES.items():
            subject_words = {word for term in signature.anchor_groups[0] for word in term.split()}
            for index, group in enumerate(signature.anchor_groups[1:], start=1):
                borrowed = sorted(term for term in group if term in subject_words)
                with self.subTest(control=control_id, group=index):
                    self.assertEqual(
                        borrowed,
                        [],
                        f"{control_id} group {index} borrows {borrowed} from its own "
                        f"subject, so one phrase satisfies both groups.",
                    )


class EverySignatureCanFire(unittest.TestCase):
    def test_the_corpus_covers_every_control_in_the_framework(self):
        self.assertEqual(set(SENTENCES), set(FRAMEWORK.ids))

    def test_each_control_matches_its_own_sentence(self):
        for control_id, sentence in SENTENCES.items():
            with self.subTest(control=control_id):
                coverage = evaluate_sentence(sentence)[control_id]
                self.assertIs(
                    coverage,
                    Coverage.ADDRESSED,
                    f"{control_id} came back {coverage.value} on: {sentence}",
                )


class CrossTalkIsDeclaredOrItIsADefect(unittest.TestCase):
    def test_no_sentence_lights_up_a_control_it_has_nothing_to_do_with(self):
        for control_id, sentence in SENTENCES.items():
            with self.subTest(control=control_id):
                also = {
                    other
                    for other, coverage in evaluate_sentence(sentence).items()
                    if coverage is Coverage.ADDRESSED and other != control_id
                }
                unexpected = also - ALLOWED_CROSSTALK.get(control_id, set())
                self.assertEqual(
                    unexpected,
                    set(),
                    f"{control_id} sentence also claims {sorted(unexpected)}: {sentence}",
                )


if __name__ == "__main__":
    unittest.main()
