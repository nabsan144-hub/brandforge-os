export function productPhotoDimensions(bytes){
 const b=new Uint8Array(bytes),v=new DataView(b.buffer,b.byteOffset,b.byteLength);let width=0,height=0;
 if(b.length>=24&&b.slice(0,8).every((x,i)=>x===[137,80,78,71,13,10,26,10][i])){width=v.getUint32(16);height=v.getUint32(20);}
 else if(b[0]===255&&b[1]===216){
  let i=2;
  while(i+4<b.length){
   if(b[i++]!==255)break;while(b[i]===255)i++;const marker=b[i++];
   if(marker===217||marker===218)break;
   const length=v.getUint16(i);if(length<2||i+length>b.length)break;
   if([192,193,194].includes(marker)&&length>=8){height=v.getUint16(i+3);width=v.getUint16(i+5);break;}i+=length;
  }
 }
 if(!width||!height||width*height>4_000_000)throw new Error('Use a complete PNG or JPEG with at most 4 million pixels.');
 return {width,height};
}
