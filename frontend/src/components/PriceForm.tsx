import { useState, type FormEvent } from 'react';
import {
  ArrowRight,
  Check,
  ChevronDown,
  LoaderCircle,
  SlidersHorizontal,
  Smartphone,
  Sparkles,
} from 'lucide-react';
import catalogData from '../data/models.json';
import type { Condition, Phone } from '../lib/api';

const catalog: Record<string, string[]> = catalogData;
interface Props {
  busy: boolean;
  onSubmit: (phone: Phone, price?: number) => void;
  onEdit: () => void;
}
export default function PriceForm({ busy, onSubmit, onEdit }: Props) {
  const [brand, setBrand] = useState('Apple');
  const [model, setModel] = useState('');
  const [condition, setCondition] = useState<Condition>('used');
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const number = (key: string) =>
      data.get(key) ? Number(data.get(key)) : undefined;
    onSubmit(
      {
        brand: brand.trim(),
        model: model.trim(),
        condition,
        storage_gb: number('storage'),
        ram_gb: number('ram'),
        photo_count: number('photos'),
        city: String(data.get('city') || '').trim() || undefined,
        seller_type: (data.get('seller') || undefined) as Phone['seller_type'],
      },
      number('price'),
    );
  }
  return (
    <form onSubmit={submit} onChange={onEdit}>
      <fieldset disabled={busy}>
        <div className='form-heading'>
          <h2>Tell us about the phone</h2>
          <p>A few details are all you need to get started.</p>
        </div>
        <div className='field-grid'>
          <label className='field'>
            Brand
            <div className='input-wrap'>
              <input
                name='brand'
                list='brands'
                value={brand}
                required
                maxLength={120}
                placeholder='e.g. Apple'
                autoComplete='off'
                onChange={(e) => {
                  setBrand(e.target.value);
                  setModel('');
                }}
              />
              <ChevronDown size={16} />
            </div>
            <datalist id='brands'>
              {Object.keys(catalog).map((b) => (
                <option key={b} value={b} />
              ))}
            </datalist>
          </label>
          <label className='field'>
            Model
            <div className='input-wrap'>
              <input
                name='model'
                list='models'
                value={model}
                required
                maxLength={120}
                placeholder={
                  brand === 'Apple'
                    ? 'e.g. iPhone 13'
                    : 'Choose or type a model'
                }
                autoComplete='off'
                onChange={(e) => setModel(e.target.value)}
              />
              <ChevronDown size={16} />
            </div>
            <datalist id='models'>
              {(catalog[brand] || []).map((m) => (
                <option key={m} value={m} />
              ))}
            </datalist>
          </label>
        </div>
        <div className='field condition-field'>
          <span id='condition-label'>Condition</span>
          <div
            className='condition-options'
            role='radiogroup'
            aria-labelledby='condition-label'
          >
            {(['used', 'new'] as const).map((value) => (
              <label
                className={`condition-option ${condition === value ? 'selected' : ''}`}
                key={value}
              >
                <input
                  type='radio'
                  name='condition'
                  value={value}
                  checked={condition === value}
                  onChange={() => {
                    setCondition(value);
                    onEdit();
                  }}
                />
                <span className='condition-icon'>
                  {value === 'used' ? (
                    <Smartphone size={20} />
                  ) : (
                    <Sparkles size={20} />
                  )}
                </span>
                <span>
                  <strong>{value === 'used' ? 'Used' : 'New'}</strong>
                  <small>
                    {value === 'used' ? 'Previously owned' : 'Never used'}
                  </small>
                </span>
                <span className='radio-mark'>
                  {condition === value && <Check size={12} />}
                </span>
              </label>
            ))}
          </div>
        </div>
        <div className='field-grid'>
          <label className='field'>
            Storage <span className='optional'>Optional</span>
            <select name='storage' defaultValue=''>
              <option value=''>Not sure</option>
              {[4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048].map((n) => (
                <option key={n} value={n}>
                  {n >= 1024 ? `${n / 1024} TB` : `${n} GB`}
                </option>
              ))}
            </select>
          </label>
          <label className='field'>
            Asking price <span className='optional'>Optional</span>
            <div className='input-wrap'>
              <input
                name='price'
                type='number'
                min='0.01'
                step='0.01'
                placeholder='e.g. 650'
                inputMode='decimal'
              />
              <span className='input-unit'>₼</span>
            </div>
          </label>
        </div>
        <p className='field-hint'>
          Add an asking price to see if it looks fair.
        </p>
        <details className='more-details'>
          <summary>
            <SlidersHorizontal size={16} /> More details <span>Optional</span>
            <ChevronDown size={16} />
          </summary>
          <div className='field-grid detail-fields'>
            <label className='field'>
              RAM (GB)
              <input
                name='ram'
                type='number'
                min='1'
                step='1'
                placeholder='Not sure'
                inputMode='numeric'
              />
            </label>
            <label className='field'>
              City
              <input name='city' maxLength={120} placeholder='e.g. Bakı' />
            </label>
            <label className='field'>
              Seller
              <select name='seller' defaultValue=''>
                <option value=''>Not sure</option>
                <option value='shop'>Shop</option>
                <option value='private'>Individual</option>
              </select>
            </label>
            <label className='field'>
              Listing photos
              <input
                name='photos'
                type='number'
                min='0'
                step='1'
                placeholder='Not sure'
                inputMode='numeric'
              />
            </label>
          </div>
        </details>
        <button className='primary-button' type='submit'>
          {busy ? (
            <>
              <LoaderCircle size={18} className='spin' /> Estimating price…
            </>
          ) : (
            <>
              Get price estimate <ArrowRight size={18} />
            </>
          )}
        </button>
      </fieldset>
    </form>
  );
}
