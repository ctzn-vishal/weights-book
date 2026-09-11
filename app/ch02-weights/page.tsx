import { chapterPage } from '@/lib/chapter-page';
import Article from './article.mdx';

const { metadata, Page } = chapterPage('ch02-weights', Article);
export { metadata };
export default Page;
