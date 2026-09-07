import {billingReadiness} from '../api/_lib/commerce.js';
console.log(JSON.stringify({cloud:billingReadiness('cloud'),desktop:billingReadiness('desktop')},null,2));
