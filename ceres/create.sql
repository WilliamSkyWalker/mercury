CREATE TABLE Testcase (
                          id INT AUTO_INCREMENT PRIMARY KEY,
                          pre_request_script TEXT,
                          post_request_script TEXT,
                          type VARCHAR(100),
                          method VARCHAR(100),
                          url VARCHAR(500),
                          headers TEXT,
                          params TEXT,
                          body TEXT,
                          auth TEXT,
                          case_name VARCHAR(100),
                          assertion TEXT,
                          folder VARCHAR(100),
                          comment TEXT,
                          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                          updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE folder (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        name VARCHAR(100) NOT NULL,
                        father_folder VARCHAR(100) NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);