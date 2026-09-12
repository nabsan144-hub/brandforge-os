import {HttpError} from './http.js';
export function needsVisualReview(row){
 return row.visual_review_state!=='unchanged' && !(Number.isInteger(row.revision)&&row.visual_review_ack_revision===row.revision&&row.visual_review_ack_at);
}
export function requireVisualReviewClient(req,row){
 if(row.visual_version_id&&req.headers?.get?.('x-brandforge-visuals')!=='vector-corrections-v1')throw new HttpError(409,'Reload BrandForge to review saved visual corrections and their version history.','CLIENT_UPDATE_REQUIRED');
 // Even acknowledged stale visuals must retain their warning in an export.
 if(row.visual_review_state==='unchanged')return;
 if(req.headers?.get?.('x-brandforge-review')!=='visual-review-v1')throw new HttpError(409,'Reload BrandForge to review copy and visual differences before downloading.','CLIENT_UPDATE_REQUIRED');
}
