import { ImageResponse } from 'next/og';

export const size = { width: 32, height: 32 };
export const contentType = 'image/png';

export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: 32,
          height: 32,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'linear-gradient(135deg, #AFC7E8, #A8D5C2)',
          borderRadius: 8,
        }}
      >
        <svg
          width="20"
          height="20"
          viewBox="0 0 22 22"
          fill="none"
        >
          <polygon
            points="11,1 20.5,6 20.5,16 11,21 1.5,16 1.5,6"
            stroke="#050507"
            stroke-width="1.8"
            fill="transparent"
          />
          <polygon
            points="11,5.5 17,9 17,13 11,16.5 5,13 5,9"
            stroke="#050507"
            stroke-width="1.2"
            fill="none"
            stroke-opacity="0.5"
          />
        </svg>
      </div>
    ),
    { ...size },
  );
}
