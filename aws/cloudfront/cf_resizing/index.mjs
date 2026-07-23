import sharp from 'sharp';
import client from 'aws-sdk';

const s3 = new client.S3({
  region: 'ap-northeast-2'
});
const BUCKET = '<S3_BUCKET_NAME>';

export async function handler(event, _, callback) {
  const { request, response } = event.Records[0].cf;

  // 만약 response 객체가 정의되지 않았다면 초기화
  if (!response) {
    return callback(null, {
      status: '500',
      statusDescription: 'Internal Server Error',
      body: 'Response object is undefined'
    });
  }

  /** 쿼리 설명
   * w : width
   * h : height
   * f : format
   * q : quality
   * t : type (contain, cover, fill, inside, outside)
   */
  const querystring = request.querystring;
  const searchParams = new URLSearchParams(querystring);

  if (!searchParams.get('w') && !searchParams.get('h')) {
    return callback(null, response);
  }

  const { uri } = request;
  const [, imageName, extension] = uri.match(/\/?(.*)\.(.*)/);

  const width = parseInt(searchParams.get('w'), 10);
  const height = parseInt(searchParams.get('h'), 10);
  const quality = parseInt(searchParams.get('q'), 10) || DEFAULT_QUALITY;
  const type = searchParams.get('t') || DEFAULT_TYPE;
  const f = searchParams.get('f');
  const format = (f === 'jpg' ? 'jpeg' : f) || extension;

  try {
    const s3Object = await getS3Object(s3, BUCKET, imageName, extension);
    const resizedImage = await resizeImage(s3Object, width, height, format, quality);

    response.status = 200;
    response.body = resizedImage.toString('base64');
    response.bodyEncoding = 'base64';
    response.headers['content-type'] = [
      {
        key: 'Content-Type',
        value: `image/${format}`
      }
    ];
    response.headers['cache-control'] = [{ key: 'cache-control', value: 'max-age=31536000' }];
    return callback(null, response);

  } catch (error) {
    console.log('Error: ', error);
    return callback(null, {
      status: '500',
      statusDescription: 'Internal Server Error',
      body: `Error processing the image: ${error.message}`
    });
  }
}

const DEFAULT_QUALITY = 80;
const DEFAULT_TYPE = 'cover'; // 기본 타입을 'cover'로 설정

async function getS3Object(s3, bucket, imageName, extension) {
  try {
    const s3Object = await s3.getObject({
      Bucket: bucket,
      Key: decodeURI(imageName + '.' + extension)
    }).promise();

    return s3Object;
  } catch (error) {
    console.log('s3.getObject error: ', error);
    throw new Error(error);
  }
}

async function resizeImage(s3Object, width, height, format, quality) {
  try {
    const resizedImage = await sharp(s3Object.Body)
      .resize(width, height, { fit: 'cover' }) // 'cover' 옵션 사용
      .toFormat(format, {
        quality
      })
      .toBuffer();

    return resizedImage;
  } catch (error) {
    console.log('resizeImage error: ', error);
    throw new Error(error);
  }
}