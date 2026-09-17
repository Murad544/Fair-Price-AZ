import {
  ArrowUpRight,
  BadgeCheck,
  Check,
  CircleHelp,
  ExternalLink,
  LoaderCircle,
  Minus,
  Smartphone,
  TrendingDown,
} from 'lucide-react';
import type { Result } from '../lib/api';

const money = (value: number) =>
  new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 }).format(value);
interface Props {
  result: Result | null;
  busy: boolean;
  mode: 'link' | 'manual';
}
export default function ResultCard({ result, busy, mode }: Props) {
  const prediction = result?.prediction;
  const diff = prediction?.difference_pct;
  const state = prediction?.verdict?.startsWith('Overpriced')
    ? 'high'
    : prediction?.verdict?.startsWith('Good deal')
      ? 'low'
      : 'fair';
  const compare = prediction?.actual_price_azn != null;
  return (
    <aside
      className={`result-card ${result ? 'has-result' : ''}`}
      aria-label='Price check result'
      aria-live='polite'
      aria-busy={busy}
    >
      <div className='result-top'>
        <span>
          <span className='status-dot' /> YOUR PRICE CHECK
        </span>
        <span className='currency-tag'>AZN ₼</span>
      </div>
      {busy ? (
        <div className='result-empty loading-result'>
          <div className='loading-orbit'>
            <LoaderCircle size={38} className='spin' />
          </div>
          <h2>
            {mode === 'link' ? 'Taking a closer look' : 'Finding your estimate'}
          </h2>
          <p>
            {mode === 'link'
              ? 'Reading the listing and checking the phone’s details. This can take up to a minute.'
              : 'Comparing the phone’s details with patterns in local asking prices.'}
          </p>
          <div className='loading-line' />
        </div>
      ) : result && prediction ? (
        <div className='result-content'>
          <div className='phone-title'>
            <span className='small-icon'>
              <Smartphone size={23} />
            </span>
            <div>
              <h2>
                {result.phone.brand === 'Apple'
                  ? result.phone.model
                  : `${result.phone.brand} ${result.phone.model}`}
              </h2>
              <p>
                {prediction.condition === 'used' ? 'Used' : 'New'} phone
                {result.phone.storage_gb
                  ? ` · ${result.phone.storage_gb >= 1024 ? `${result.phone.storage_gb / 1024} TB` : `${result.phone.storage_gb} GB`}`
                  : ''}
              </p>
            </div>
          </div>
          <div className='price-estimate'>
            <span>Estimated asking price</span>
            <div>
              {money(prediction.predicted_price_azn)} <span>₼</span>
            </div>
            <p>A model estimate for this phone’s details</p>
          </div>
          {compare ? (
            <>
              <div className='asking-row'>
                <span>Seller’s asking price</span>
                <strong>{money(prediction.actual_price_azn!)} ₼</strong>
              </div>
              <div className={`verdict verdict-${state}`}>
                <span>
                  {state === 'high' ? (
                    <ArrowUpRight size={23} />
                  ) : state === 'low' ? (
                    <TrendingDown size={23} />
                  ) : (
                    <BadgeCheck size={23} />
                  )}
                </span>
                <div>
                  <strong>
                    {state === 'high'
                      ? 'Priced above the estimate'
                      : state === 'low'
                        ? 'A potential good deal'
                        : 'Looks fairly priced'}
                  </strong>
                  <p>
                    {diff === 0
                      ? 'Matches the estimated price'
                      : `${Math.abs(diff ?? 0).toFixed(1)}% ${(diff ?? 0) > 0 ? 'above' : 'below'} the estimate`}
                  </p>
                </div>
              </div>
              <p className='comparison-note'>
                We use a {prediction.condition === 'used' ? '15%' : '5%'} margin
                for {prediction.condition} phones.
              </p>
            </>
          ) : (
            <div className='no-comparison'>
              <CircleHelp size={18} />
              <p>
                Have an asking price? Add it to the form to see how it compares.
              </p>
            </div>
          )}
          {result.url && (
            <a
              className='listing-link'
              href={result.url}
              target='_blank'
              rel='noopener noreferrer'
            >
              View original listing <ExternalLink size={14} />
            </a>
          )}
          <div className='result-disclaimer'>
            <CircleHelp size={16} />
            <p>
              This is an estimate, not a valuation. Battery health, repairs, and
              phone condition can change the price. Inspect before buying.
            </p>
          </div>
        </div>
      ) : (
        <div className='result-empty'>
          <div className='phone-scene' aria-hidden='true'>
            <div className='scene-ring ring-one' />
            <div className='scene-ring ring-two' />
            <div className='phone-art'>
              <div className='phone-camera' />
              <div className='phone-art-check'>
                <Check size={26} strokeWidth={2.5} />
              </div>
              <div className='phone-art-line' />
              <div className='phone-art-line short' />
              <div className='phone-art-dots'>
                <Minus />
                <Minus />
                <Minus />
              </div>
            </div>
            <div className='floating-tag'>
              <BadgeCheck size={15} /> Know your price
            </div>
            <span className='scene-spark spark-one'>+</span>
            <span className='scene-spark spark-two'>+</span>
          </div>
          <h2>A little clarity before you buy.</h2>
          <p>
            Check a listing or enter phone details.
            <br />
            Your estimate will appear right here.
          </p>
          <div className='empty-result-label'>
            <span /> MADE FOR AZERBAIJAN
          </div>
        </div>
      )}
    </aside>
  );
}
