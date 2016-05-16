$data_version = '3.2';
%repos = (
  '@all' => {
    '@all' => [
      [
        1,
        '-',
        'VREF/update-block-push-origin'
      ],
      [
        4,
        'R',
        'refs/.*'
      ]
    ],
    '@cvsadmin' => [
      [
        2,
        'RWC',
        'refs/.*'
      ]
    ]
  }
);
%configs = (
  '@all' => [
    [
      3,
      'gitolite-options.CREATE_IS_C',
      '1'
    ]
  ]
);
%groups = (
  'copr-dist-git' => [
    '@cvsadmin'
  ]
);
