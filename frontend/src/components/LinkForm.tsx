import { useState, type FormEvent } from 'react';
import {
  ArrowRight,
  Clipboard,
  Link2,
  LoaderCircle,
  CircleCheck,
  Smartphone,
} from 'lucide-react';
import { normalizeListingUrl } from '../lib/api';

interface Props {
  busy: boolean;
  onSubmit: (url: string) => void;
  onEdit: () => void;
  onManual: () => void;
}
export default function LinkForm({ busy, onSubmit, onEdit, onManual }: Props) {
  const [url, setUrl] = useState('');
  const [message, setMessage] = useState('');
  async function paste() {
    try {
      setUrl(await navigator.clipboard.readText());
      setMessage('');
      onEdit();
    } catch {
      setMessage(
        'Use your keyboard or press and hold the field to paste your link.',
      );
    }
  }
  function submit(event: FormEvent) {
    event.preventDefault();
    try {
      const canonical = normalizeListingUrl(url);
      setMessage('');
      onSubmit(canonical);
    } catch (error) {
      setMessage((error as Error).message);
    }
  }
  return (
    <form onSubmit={submit}>
      <fieldset disabled={busy}>
        <div className='form-heading'>
          <h2>Found a phone you like?</h2>
          <p>Paste its Tap.az link. We’ll take a look at the price.</p>
        </div>
        <label className='field' htmlFor='listing-url'>
          Tap.az listing link
        </label>
        <div className={`url-input ${message ? 'has-error' : ''}`}>
          <Link2 size={19} aria-hidden='true' />
          <input
            id='listing-url'
            name='url'
            type='text'
            inputMode='url'
            required
            value={url}
            placeholder='https://tap.az/elanlar/…'
            autoComplete='off'
            spellCheck={false}
            aria-describedby='link-help link-message'
            aria-invalid={!!message}
            onChange={(e) => {
              setUrl(e.target.value);
              setMessage('');
              onEdit();
            }}
          />
          <button
            type='button'
            onClick={paste}
            className='paste-button'
            aria-label='Paste link from clipboard'
          >
            <Clipboard size={15} />
            <span>Paste</span>
          </button>
        </div>
        <p id='link-help' className='field-hint'>
          Open a phone listing on Tap.az and copy its link.
        </p>
        <p
          id='link-message'
          className='inline-error'
          role={message ? 'alert' : undefined}
        >
          {message}
        </p>
        <button className='primary-button' type='submit'>
          {busy ? (
            <>
              <LoaderCircle size={18} className='spin' /> Checking the listing…
            </>
          ) : (
            <>
              Check this price <ArrowRight size={18} />
            </>
          )}
        </button>
        <div className='link-benefits'>
          <span>
            <CircleCheck size={15} /> Phone details filled for you
          </span>
          <span>
            <CircleCheck size={15} /> New & used phones
          </span>
        </div>
        <div className='manual-prompt'>
          <span className='small-icon'>
            <Smartphone size={22} />
          </span>
          <div>
            <strong>No link? No problem.</strong>
            <p>Check a phone using its details.</p>
          </div>
          <button
            type='button'
            onClick={onManual}
            aria-label='Enter details manually'
          >
            <ArrowRight size={19} />
          </button>
        </div>
      </fieldset>
    </form>
  );
}
