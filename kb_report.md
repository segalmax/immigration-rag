# USCIS Policy Manual — Knowledge Base Quality Report

**Corpus:** `uscis_policy_manual/`

---

## 1. Summary

| Metric | Value |
|--------|-------|
| Total files | 494 |
| Reserved stubs (excluded) | 48 |
| Clean files | 446 |
| Total words (clean files) | 950,338 |
| Mean words/file | 2,131 |
| Median words/file | 1,311 |
| Min words/file | 67 |
| Max words/file | 15,832 |

---

## 2. Word Count Distribution (clean files only)

| Range | Files | Bar |
|-------|-------|-----|
| < 100 | 5 | █ |
| 100–499 | 69 | ███████████████████████ |
| 500–1,999 | 216 | ████████████████████████████████████████████████████████████████████████ |
| 2,000–4,999 | 117 | ███████████████████████████████████████ |
| 5,000–7,999 | 25 | ████████ |
| 8,000+ | 14 | ████ |

---

## 3. Oversized Files (≥ 8,000 words)

*These exceed typical embedding model context windows. Flag for splitting at `##` section level in the chunking phase.*

| Words | Sections | File |
|-------|----------|------|
| 15,832 | 10 | `volume_3_humanitarian_protection_and_parole/part_d_violence_against_women_act/chapter_2_eligibility_requirements_and_evidence.md` |
| 13,901 | 6 | `volume_6_immigrants/part_g_investors/chapter_2_immigrant_petition_eligibility_requirements.md` |
| 13,203 | 8 | `volume_12_citizenship_and_naturalization/part_d_general_naturalization_requirements/chapter_2_lawful_permanent_resident_admission_for_naturalization.md` |
| 12,255 | 5 | `volume_6_immigrants/part_f_employment_based_classifications/chapter_5_advanced_degree_or_exceptional_ability.md` |
| 12,035 | 7 | `volume_2_nonimmigrants/part_m_nonimmigrants_of_extraordinary_ability_or_achievement_o/chapter_4_o_1_beneficiaries.md` |
| 11,461 | 12 | `volume_1_general_policies_and_procedures/part_a_public_services/chapter_7_privacy_and_confidentiality.md` |
| 11,070 | 14 | `volume_12_citizenship_and_naturalization/part_f_good_moral_character/chapter_5_conditional_bars_for_acts_in_statutory_period.md` |
| 10,984 | 10 | `volume_7_adjustment_of_status/part_a_adjustment_of_status_policies_and_procedures/chapter_7_child_status_protection_act.md` |
| 10,630 | 5 | `volume_6_immigrants/part_b_family_based_immigrants/chapter_6_spouses.md` |
| 10,613 | 9 | `volume_3_humanitarian_protection_and_parole/part_b_victims_of_trafficking/chapter_2_eligibility_requirements.md` |
| 10,400 | 7 | `volume_7_adjustment_of_status/part_b_245a_adjustment/chapter_2_eligibility_requirements.md` |
| 10,284 | 8 | `volume_1_general_policies_and_procedures/part_e_adjudications/chapter_6_evidence.md` |
| 8,737 | 3 | `volume_6_immigrants/part_f_employment_based_classifications/chapter_2_extraordinary_ability.md` |
| 8,613 | 5 | `volume_1_general_policies_and_procedures/part_e_adjudications/chapter_8_discretionary_analysis.md` |

---

## 4. Reserved Stubs (48 files — excluded from clean corpus)

*These are USCIS placeholder chapters not yet written. Content is only `_No content._`.*

- `volume_10_employment_authorization/part_a_employment_authorization_policies_and_procedures/chapter_3_documentation_and_evidence_reserved.md`
- `volume_10_employment_authorization/part_a_employment_authorization_policies_and_procedures/chapter_5_reserved.md`
- `volume_10_employment_authorization/part_a_employment_authorization_policies_and_procedures/chapter_6_card_production_and_card_correction_reserved.md`
- `volume_10_employment_authorization/part_a_employment_authorization_policies_and_procedures/chapter_7_post_decision_actions_reserved.md`
- `volume_10_employment_authorization/part_b_specific_categories/chapter_4_reserved.md`
- `volume_1_general_policies_and_procedures/part_c_biometrics_collection_and_security_checks/chapter_3_security_checks_reserved.md`
- `volume_1_general_policies_and_procedures/part_e_adjudications/chapter_7_interviews_reserved.md`
- `volume_2_nonimmigrants/part_a_nonimmigrant_policies_and_procedures/chapter_2_general_requirements_reserved.md`
- `volume_2_nonimmigrants/part_a_nonimmigrant_policies_and_procedures/chapter_3_maintaining_status_reserved.md`
- `volume_2_nonimmigrants/part_i_temporary_agricultural_and_nonagricultural_workers_h_2/chapter_10_post_adjudication_issues_related_to_temporary_nonagricultural_worker_h_2b_petitions_reserved.md`
- `volume_2_nonimmigrants/part_i_temporary_agricultural_and_nonagricultural_workers_h_2/chapter_2_eligibility_for_temporary_agricultural_worker_h_2a_classification_reserved.md`
- `volume_2_nonimmigrants/part_i_temporary_agricultural_and_nonagricultural_workers_h_2/chapter_3_documentation_and_evidence_for_temporary_agricultural_worker_h_2a_classification_reserved.md`
- `volume_2_nonimmigrants/part_i_temporary_agricultural_and_nonagricultural_workers_h_2/chapter_4_adjudication_of_temporary_agricultural_worker_h_2a_petitions_reserved.md`
- `volume_2_nonimmigrants/part_i_temporary_agricultural_and_nonagricultural_workers_h_2/chapter_5_post_adjudication_issues_related_to_temporary_agricultural_worker_h_2a_petitions_reserved.md`
- `volume_2_nonimmigrants/part_i_temporary_agricultural_and_nonagricultural_workers_h_2/chapter_6_temporary_agricultural_worker_h_2a_petitions_requiring_special_handling_reserved.md`
- `volume_2_nonimmigrants/part_i_temporary_agricultural_and_nonagricultural_workers_h_2/chapter_7_eligibility_for_temporary_nonagricultural_worker_h_2b_classification_reserved.md`
- `volume_2_nonimmigrants/part_i_temporary_agricultural_and_nonagricultural_workers_h_2/chapter_8_documentation_and_evidence_for_temporary_nonagricultural_worker_h_2b_classification_reserved.md`
- `volume_2_nonimmigrants/part_i_temporary_agricultural_and_nonagricultural_workers_h_2/chapter_9_adjudication_of_temporary_nonagricultural_worker_h_2b_petitions_reserved.md`
- `volume_3_humanitarian_protection_and_parole/part_c_victims_of_crimes/chapter_3_documentation_and_evidence_reserved.md`
- `volume_3_humanitarian_protection_and_parole/part_c_victims_of_crimes/chapter_8_post_adjudicative_matters_reserved.md`
- `volume_6_immigrants/part_b_family_based_immigrants/chapter_8_parents_of_us_citizens_reserved.md`
- `volume_6_immigrants/part_b_family_based_immigrants/chapter_9_siblings_of_us_citizens_reserved.md`
- `volume_6_immigrants/part_e_employment_based_immigration/chapter_5_reserved.md`
- `volume_6_immigrants/part_h_designated_and_special_immigrants/chapter_4_certain_physicians_reserved.md`
- `volume_6_immigrants/part_h_designated_and_special_immigrants/chapter_5_certain_g_4_or_nato_6_employees_and_their_family_members_reserved.md`
- `volume_6_immigrants/part_h_designated_and_special_immigrants/chapter_7_certain_broadcasters_reserved.md`
- `volume_7_adjustment_of_status/part_e_employment_based_adjustment/chapter_1_purpose_and_background_reserved.md`
- `volume_7_adjustment_of_status/part_e_employment_based_adjustment/chapter_2_eligibility_requirements_reserved.md`
- `volume_7_adjustment_of_status/part_e_employment_based_adjustment/chapter_3_immigrant_visa_availability_and_priority_dates_reserved.md`
- `volume_7_adjustment_of_status/part_e_employment_based_adjustment/chapter_4_documentation_and_evidence_reserved.md`
- `volume_7_adjustment_of_status/part_e_employment_based_adjustment/chapter_6_adjudication_reserved.md`
- `volume_7_adjustment_of_status/part_e_employment_based_adjustment/chapter_7_national_interest_waiver_physicians_reserved.md`
- `volume_7_adjustment_of_status/part_p_other_adjustment_programs/chapter_10_reserved.md`
- `volume_7_adjustment_of_status/part_p_other_adjustment_programs/chapter_1_reserved.md`
- `volume_7_adjustment_of_status/part_p_other_adjustment_programs/chapter_2_reserved.md`
- `volume_7_adjustment_of_status/part_p_other_adjustment_programs/chapter_3_reserved.md`
- `volume_7_adjustment_of_status/part_p_other_adjustment_programs/chapter_4_reserved.md`
- `volume_7_adjustment_of_status/part_p_other_adjustment_programs/chapter_6_reserved.md`
- `volume_7_adjustment_of_status/part_p_other_adjustment_programs/chapter_7_reserved.md`
- `volume_7_adjustment_of_status/part_p_other_adjustment_programs/chapter_8_reserved.md`
- `volume_8_admissibility/part_f_national_security_and_related_grounds_of_inadmissibility/chapter_1_purpose_and_background_reserved.md`
- `volume_8_admissibility/part_f_national_security_and_related_grounds_of_inadmissibility/chapter_2_reserved.md`
- `volume_8_admissibility/part_o_aliens_unlawfully_present/chapter_1_purpose_and_background_reserved.md`
- `volume_8_admissibility/part_o_aliens_unlawfully_present/chapter_2_reserved.md`
- `volume_8_admissibility/part_o_aliens_unlawfully_present/chapter_3_reserved.md`
- `volume_8_admissibility/part_o_aliens_unlawfully_present/chapter_4_reserved.md`
- `volume_8_admissibility/part_o_aliens_unlawfully_present/chapter_5_reserved.md`
- `volume_9_waivers_and_other_forms_of_relief/part_o_victims_of_trafficking/chapter_1_purpose_and_background_reserved.md`

---

## 5. Footnote Noise

- **Total inline `**[n]**` refs across all files:** 9,657
- **Files with at least one ref:** 443

**Top 10 files by footnote ref count:**

| Refs | File |
|------|------|
| 182 | `volume_3_humanitarian_protection_and_parole/part_d_violence_against_women_act/chapter_2_eligibility_requirements_and_evidence.md` |
| 151 | `volume_12_citizenship_and_naturalization/part_d_general_naturalization_requirements/chapter_2_lawful_permanent_resident_admission_for_naturalization.md` |
| 141 | `volume_12_citizenship_and_naturalization/part_f_good_moral_character/chapter_5_conditional_bars_for_acts_in_statutory_period.md` |
| 140 | `volume_6_immigrants/part_g_investors/chapter_2_immigrant_petition_eligibility_requirements.md` |
| 125 | `volume_7_adjustment_of_status/part_b_245a_adjustment/chapter_2_eligibility_requirements.md` |
| 112 | `volume_6_immigrants/part_b_family_based_immigrants/chapter_6_spouses.md` |
| 106 | `volume_1_general_policies_and_procedures/part_e_adjudications/chapter_6_evidence.md` |
| 104 | `volume_6_immigrants/part_f_employment_based_classifications/chapter_5_advanced_degree_or_exceptional_ability.md` |
| 99 | `volume_8_admissibility/part_g_public_charge_ground_of_inadmissibility/chapter_6_affidavit_of_support_under_section_213a_of_the_ina.md` |
| 96 | `volume_3_humanitarian_protection_and_parole/part_b_victims_of_trafficking/chapter_2_eligibility_requirements.md` |

---

## 6. Table Breakdown

| Metric | Count |
|--------|-------|
| Files containing tables | 152 |
| Single-column tables (eligibility checklists) | 72 |
| Multi-column tables | 247 |
| Table rows with flattened list items (`- a - b - c`) | 264 |

*Flattened list rows occur when HTML `<ul><li>` inside `<td>` is converted. Text is preserved but formatting is cramped. Acceptable for now.*

---

## 7. Per-Volume Summary

| Volume | Files | Stubs | Clean | Total Words | Median Words |
|--------|-------|-------|-------|-------------|--------------|
| `volume_10_employment_authorization` | 11 | 5 | 6 | 14,225 | 416 |
| `volume_11_travel_and_identity_documents` | 9 | 0 | 9 | 10,639 | 906 |
| `volume_12_citizenship_and_naturalization` | 64 | 0 | 64 | 142,597 | 1,308 |
| `volume_1_general_policies_and_procedures` | 32 | 2 | 30 | 72,563 | 924 |
| `volume_2_nonimmigrants` | 85 | 11 | 74 | 114,047 | 778 |
| `volume_3_humanitarian_protection_and_parole` | 36 | 2 | 34 | 79,830 | 1,142 |
| `volume_4_refugees_and_asylees` | 5 | 0 | 5 | 10,936 | 2,305 |
| `volume_5_adoptions` | 39 | 0 | 39 | 65,297 | 1,363 |
| `volume_6_immigrants` | 58 | 6 | 52 | 158,441 | 1,746 |
| `volume_7_adjustment_of_status` | 82 | 14 | 68 | 170,694 | 1,364 |
| `volume_8_admissibility` | 45 | 7 | 38 | 77,662 | 1,187 |
| `volume_9_waivers_and_other_forms_of_relief` | 28 | 1 | 27 | 34,742 | 852 |
