import {it,expect,vi} from 'vitest';
const getUser=vi.hoisted(()=>vi.fn());
vi.mock('@supabase/supabase-js',()=>({createClient:()=>({auth:{getUser}})}));
import {authUser} from '../api/_lib/sb.js';
const request=new Request('https://example.test',{headers:{Authorization:'Bearer fixture'}});
it('does not disguise an auth outage as an invalid session',async()=>{getUser.mockResolvedValue({error:{status:503},data:{}});await expect(authUser(request)).rejects.toMatchObject({status:503});getUser.mockResolvedValue({error:{status:401},data:{}});expect(await authUser(request)).toBeNull();});
