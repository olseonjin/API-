create schema nathing;
use nathing;
CREATE TABLE user (
    id INT PRIMARY KEY AUTO_INCREMENT,
    userid VARCHAR(20) NOT NULL UNIQUE,
    user_nickname VARCHAR(20) NOT NULL UNIQUE,
    password VARCHAR(30) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
drop table user;
CREATE TABLE post (
    id INT PRIMARY KEY AUTO_INCREMENT,
    content TEXT NOT NULL,
    image_url VARCHAR(255),
    user_nickname VARCHAR(20) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    exited_at DATETIME,
    like_count INT DEFAULT 0,
    CONSTRAINT fk_post_user_nickname
      FOREIGN KEY (user_nickname)
      REFERENCES user(user_nickname)
      ON DELETE CASCADE
);

DELIMITER //

CREATE TRIGGER trg_set_exited_at
BEFORE INSERT ON post
FOR EACH ROW
BEGIN
  IF NEW.exited_at IS NULL THEN
    SET NEW.exited_at = DATE_ADD(NOW(), INTERVAL 1 DAY);
  END IF;
END //

DELIMITER ;
-- 1. 이벤트 스케줄러 켜기 (최초 1회)
SET GLOBAL event_scheduler = ON;

-- 2. 이벤트 생성
CREATE EVENT IF NOT EXISTS delete_expired_posts
ON SCHEDULE EVERY 1 HOUR
DO
  DELETE FROM post WHERE exited_at < NOW();

-- 3. 이벤트 목록 확인
SHOW EVENTS;

CREATE TABLE post_like (
    id INT PRIMARY KEY AUTO_INCREMENT,
    post_id INT NOT NULL,
    user_nickname VARCHAR(20) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_like_post
      FOREIGN KEY (post_id) REFERENCES post(id) ON DELETE CASCADE,
    CONSTRAINT fk_like_user
      FOREIGN KEY (user_nickname) REFERENCES user(user_nickname) ON DELETE CASCADE,
    UNIQUE KEY unique_like (post_id, user_nickname) -- 중복 좋아요 방지
);
select * from user;
select * from post;
select * from post_like;

INSERT INTO user (userid,user_nickname,password)
VALUES 
  ('hong','홍길동','gil'),
  ('kim','김철수','cul'),
  ('lee','이영희','yeong');
  
  INSERT INTO post (content, user_nickname)
VALUES 
  ('첫 번째 게시글', '홍길동'),
  ('두 번째 게시글', '김철수'),
  ('세 번째 게시글', '이영희');
  
  INSERT INTO post_like (post_id, user_nickname)
VALUES 
  (1, '홍길동'),
  (2, '김철수'),
  (1, '이영희');

