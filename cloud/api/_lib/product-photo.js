import {HttpError} from './http.js';
import {normalizeScene} from './scene-image.js';
export function photoInput(body){
 const value=body.product_image;
 if(!value)return '';
 if(typeof value!=='string'||value.length>220000||!/^data:image\/jpeg;base64,[A-Za-z0-9+/]+={0,2}$/.test(value))throw new HttpError(400,'Use the product-photo upload control (JPEG, prepared under 160 KB).');
 if(body.product_image_rights!==true)throw new HttpError(400,'Confirm permission to upload and use this product photograph.');
 if(body.artwork_mode!=='campaign'&&body.style!=='product-v1')throw new HttpError(400,'Use Product-first for a product photograph, or remove the photograph.');
 if(body.artwork_mode!=='campaign'&&body.visuals_ai===true)throw new HttpError(400,'Choose your product photograph or AI artwork, not both.');
 if(Buffer.from(value.split(',')[1],'base64').length>160000)throw new HttpError(413,'The prepared product photograph is too large.');
 return value;
}
export async function normalizeProductPhoto(value){
 try{
  const result=await normalizeScene(value.split(',')[1]);
  if(result.bytes>160000)throw new Error('Too large');
  return 'data:image/jpeg;base64,'+result.data;
 }catch{throw new HttpError(400,'This product photo could not be safely prepared. Use a smaller, complete photograph.','PRODUCT_PHOTO_INVALID');}
}
