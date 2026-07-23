/* The one seeded demo. Exactly one project+study per account carries
 * illustrative sample data ("how it's done"); every real study starts from
 * scratch. This is the single source of truth for that identity, shared by the
 * offline fallback (studyApi seeds only this study) and the server-seeded demo
 * (middleware creates a project with this study id, marked is_demo). Keep the
 * id in step with the backend seeder. */
export const DEMO_STUDY_ID = "demo-study";
export const DEMO_PROJECT_SLUG = "demo";

export function isDemoStudy(studyId: string): boolean {
  return studyId === DEMO_STUDY_ID;
}
