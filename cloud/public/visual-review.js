// Export safety, not DRM or automated proof that the words match the artwork.
export function needsVisualReview(c){
 return c.visual_review_state!=='unchanged' && !(Number.isInteger(c.revision)&&c.visual_review_ack_revision===c.revision&&c.visual_review_ack_at);
}
export function assertVisualReview(c){
 if(needsVisualReview(c))throw new Error('Review the copy against the existing visuals and acknowledge this version before downloading. Editing copy does not redraw artwork.');
}
export function visualReviewNote(c){
 if(c.visual_review_state==='unchanged')return 'Visuals have not been marked stale by a copy edit since generation. This is not a spelling, accuracy or layout certification.';
 if(c.visual_version_id)return 'Saved visual corrections and free-form copy are separate. Review current images, offer/terms and copy together. '+(needsVisualReview(c)?'Review is required before campaign downloads.':`The account owner acknowledged version ${c.revision} on ${c.visual_review_ack_at}; this is not an accuracy certification.`);
 const reason=c.visual_review_state==='review_required'?'Copy changed after the visuals were generated.':'Alignment of this historical campaign is unknown.';
 return reason+' The visuals have NOT been redrawn. '+(needsVisualReview(c)?'Review is required before campaign downloads.':`The account owner acknowledged version ${c.revision} on ${c.visual_review_ack_at}. This acknowledges possible differences; it does not certify correctness.`);
}
