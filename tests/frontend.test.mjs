import test from 'node:test';
import assert from 'node:assert/strict';
import { toPersianDigits, toEnglishDigits, formatToman, formatNumber, parseGroupedNumber } from '../src/utils/persianFormat.js';
import { localizedApiError, translateApiMessage } from '../src/utils/apiMessages.js';

test('Persian and Arabic input digits round-trip to canonical API strings', () => {
  assert.equal(toEnglishDigits('۰۹۱۲۱۲۳۴۵۶۷'), '09121234567');
  assert.equal(toEnglishDigits('١٢٣٤٥٫٦'), '12345.6');
  assert.equal(toPersianDigits('TRACK-00123'), 'TRACK-۰۰۱۲۳');
  assert.equal(toEnglishDigits(toPersianDigits('000024')), '000024');
  assert.equal(toPersianDigits(null), '');
});
test('Currency remains readable and Persian', () => {
  assert.equal(formatToman(125000), '۱۲۵.۰۰۰ تومان');
});
test('Backend validation is translated without exposing unknown English errors', () => {
  assert.match(translateApiMessage('Invalid or expired code. Request a new code.'), /کد ورود/);
  assert.match(localizedApiError({response:{status:400,data:{phone:['This field is required.']}}}), /شماره موبایل/);
  assert.equal(translateApiMessage('Unexpected internal text', 'خطای آزمایشی'), 'خطای آزمایشی');
  assert.match(localizedApiError({response:{status:409,data:{detail:'The shipping fee changed. Review the current fee before paying.'}}}), /هزینه ارسال تغییر/);
});

test('grouped amounts preserve numeric API values', () => {
  assert.equal(formatNumber(2000000), '۲.۰۰۰.۰۰۰');
  assert.equal(parseGroupedNumber('۲.۰۰۰.۰۰۰'), '2000000');
  assert.equal(parseGroupedNumber('۲٬۰۰۰٬۰۰۰'), '2000000');
});

import { groupOrderItems } from '../src/utils/orderItems.js';
test('matching editions group with all pending indices; other editions stay separate', () => {
  const unit = { title: 'کتاب — ناشر', price: '320000', contents: [{edition_id: 1, title: 'کتاب — ناشر', quantity: 1}], status: 'awaiting_sourcing' };
  const grouped = groupOrderItems(Array.from({length:8}, (_,index) => ({...unit,index})));
  assert.equal(grouped.length, 1);
  assert.equal(grouped[0].quantity, 8);
  assert.equal(grouped[0].total, 2560000);
  assert.deepEqual(grouped[0].pendingIndices, [0,1,2,3,4,5,6,7]);
  const mixed = groupOrderItems([{...unit,index:0,status:'ready_to_ship'},{...unit,index:1},{...unit,index:2,contents:[{edition_id:2}]}]);
  assert.equal(mixed.length, 2);
  assert.deepEqual(mixed[0].pendingIndices, [1]);
  assert.equal(mixed[0].readyCount, 1);
  const rounded = groupOrderItems([{...unit,index:0,price:'99999'}, {...unit,index:1,price:'100000'}]);
  assert.equal(rounded.length, 1);
  assert.equal(rounded[0].total, 199999);
  assert.equal(rounded[0].uniformPrice, false);
});
